"""BUI answer pipeline.

question -> processing (cleaning, product detection, follow-up context) -> hybrid retrieval
(semantic + keyword) -> ranking -> confidence gate -> generation (LLM or extractive) -> citations
-> persisted message with analytics fields. Yields Server-Sent-Event payloads for streaming.
"""
import hashlib
import logging
import re
import time
from collections.abc import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import get_cache
from app.llm.providers import ProviderUnavailable, build_provider
from app.models import Conversation, Message, Product, User
from app.models.user import ROLE_LEVEL
from app.rag import extractive
from app.rag.prompt import AnswerContext, Source, build_messages, build_sources
from app.rag.retriever import ProductMatch, detect_products, hybrid_search
from app.rag.safety import clean_user_input
from app.services.system_settings import get_setting

log = logging.getLogger(__name__)

NOT_FOUND = "I couldn't find verified information about this in the BUI knowledge base. Would you like me to research it online?"
WEB_NOT_FOUND = (
    "I couldn't find reliable information online either. Please ask an administrator to add this information to the BUI knowledge base."
)


_FOLLOW_UP_RE = re.compile(r"\b(it|its|it's|this|that|these|those|they|them|their|same|above|previous)\b", re.I)


def _is_follow_up(question: str) -> bool:
    """Only carry product context over from earlier turns when the question refers back to it."""
    return bool(_FOLLOW_UP_RE.search(question)) or len(question.split()) <= 3


def _related_questions(db: Session, products: list[Product], question: str) -> list[str]:
    out: list[str] = []
    q = question.lower()
    if len(products) == 1:
        p = products[0]
        name = p.name
        candidates = [
            (p.specifications, "spec", f"What are the specifications of {name}?"),
            (p.warranty, "warrant", f"What is the warranty for {name}?"),
            (p.installation, "install", f"How do I install {name}?"),
            (p.accessories, "accessor", f"What accessories are available for {name}?"),
            (p.troubleshooting, "problem", f"What problems can occur with {name}?"),
            (p.compatibility, "compatib", f"What is {name} compatible with?"),
            (p.features, "feature", f"What are the key features of {name}?"),
        ]
        out += [text for value, kw, text in candidates if value and kw not in q]
        if p.category_id:
            sibling = db.scalars(
                select(Product).where(Product.category_id == p.category_id, Product.id != p.id, Product.status != "archived").limit(1)
            ).first()
            if sibling:
                out.insert(1, f"What is the difference between {name} and {sibling.name}?")
    elif len(products) > 1:
        for p in products[:2]:
            out.append(f"What are the key features of {p.name}?")
        out.append(f"Which has the longer warranty, {products[0].name} or {products[1].name}?")
    return out[:4]


def _answer_cache_key(question: str, user: User, language: str, provider: str) -> str:
    norm = " ".join(question.lower().split()).rstrip("?!. ")
    h = hashlib.sha256(f"{norm}|{ROLE_LEVEL.get(user.role_name, 0)}|{language}|{provider}".encode()).hexdigest()
    return f"answer:{h}"


def _stream_generation(ctx: AnswerContext, provider_name: str, model: str | None, temperature: float, state: dict) -> Iterator[str]:
    """Streams from the configured LLM; falls back to the extractive composer if unavailable."""
    provider = build_provider(provider_name, model)
    if provider is not None:
        produced = False
        try:
            for tok in provider.stream_chat(build_messages(ctx), temperature):
                produced = True
                yield tok
            state["provider"] = f"{provider.name}:{getattr(provider, 'model', '')}"
            return
        except ProviderUnavailable as exc:
            log.warning("LLM provider failed (%s); using extractive fallback", exc)
            if produced:
                yield "\n\n_(The AI model stopped responding; the answer above may be incomplete.)_"
                state["provider"] = f"{provider.name} (interrupted)"
                return
            state["provider"] = "extractive (fallback)"
    else:
        state["provider"] = "extractive"
    yield from extractive.stream_compose(ctx)


def answer_stream(
    db: Session,
    user: User,
    conversation: Conversation,
    question: str,
    language: str = "en-US",
    web: bool = False,
    regenerate: bool = False,
) -> Iterator[dict]:
    started = time.monotonic()
    question = clean_user_input(question)
    company = get_setting(db, "company_name") or "our company"
    provider_name = get_setting(db, "llm_provider") or "extractive"
    model = get_setting(db, "llm_model")
    temperature = float(get_setting(db, "llm_temperature") or 0.1)

    # ---- persist the user message (or reuse it when regenerating) ----
    history_msgs = list(conversation.messages)
    if regenerate:
        while history_msgs and history_msgs[-1].role == "assistant":
            db.delete(history_msgs.pop())
        if not history_msgs:
            yield {"type": "error", "message": "Nothing to regenerate."}
            return
        user_msg = history_msgs[-1]
        question = user_msg.content
        history_msgs = history_msgs[:-1]
    else:
        user_msg = Message(conversation_id=conversation.id, role="user", content=question)
        db.add(user_msg)
        if not history_msgs:
            conversation.title = question[:80] + ("…" if len(question) > 80 else "")
        conversation.language = language
    db.commit()
    history = [{"role": m.role, "content": m.content} for m in history_msgs[-6:]]

    # ---- question processing: products and follow-up context ----
    match: ProductMatch = detect_products(db, question)
    retrieval_query = question
    if not match.products and not match.ambiguous and _is_follow_up(question):
        for prev in reversed([m for m in history_msgs if m.role == "user"][-3:]):
            prev_match = detect_products(db, prev.content)
            if prev_match.products:
                match = ProductMatch(products=prev_match.products)
                retrieval_query = f"{' '.join(p.name for p in prev_match.products)} {question}"
                break
    products = match.products
    product_ids = [p.id for p in products]

    yield {"type": "meta", "conversation_id": conversation.id, "conversation_title": conversation.title, "user_message_id": user_msg.id}

    def finish(content: str, sources: list[Source], answered: bool, confidence: float, provider: str, related: list[str], used_web: bool = False, research_job_id: int | None = None) -> dict:
        msg = Message(
            conversation_id=conversation.id, role="assistant", content=content, sources=[s.as_dict() for s in sources],
            related_questions=related, question=question, answered=answered, confidence=round(confidence, 3),
            used_web=used_web, product_ids=product_ids, provider=provider, latency_ms=int((time.monotonic() - started) * 1000),
        )
        db.add(msg)
        db.commit()
        return {
            "type": "done", "message_id": msg.id, "content": content, "sources": msg.sources, "related_questions": related,
            "answered": answered, "confidence": msg.confidence, "provider": provider, "used_web": used_web,
            "latency_ms": msg.latency_ms, "research_job_id": research_job_id, "created_at": msg.created_at.isoformat() if msg.created_at else None,
        }

    def emit_whole(text: str) -> Iterator[dict]:
        yield {"type": "token", "content": text}

    # ---- ambiguous product names -> clarifying question ----
    if match.ambiguous and not web:
        names = ", ".join(f"**{p.name}**" + (f" ({p.model_number})" if p.model_number else "") for p in match.ambiguous[:6])
        text = f"Several products match your question: {names}. Which one do you mean?"
        yield from emit_whole(text)
        yield finish(text, [], True, 0.5, "clarification", [f"{q.name}: {question}" for q in match.ambiguous[:3]])
        return

    # ---- online research (explicitly requested) ----
    if web:
        allowed = get_setting(db, "web_research_enabled") and (user.has_role("admin") or get_setting(db, "team_can_research_from_chat"))
        if not allowed:
            text = "Online research is disabled for your account. Please contact an administrator."
            yield from emit_whole(text)
            yield finish(text, [], False, 0.0, "policy", [])
            return
        from app.research.engine import quick_web_research

        yield {"type": "status", "message": "Researching online sources…"}
        pages, job = quick_web_research(db, question, user, products[0] if len(products) == 1 else None)
        if not pages:
            text = WEB_NOT_FOUND if job.status != "failed" else f"Online research is unavailable right now ({job.error}). " + WEB_NOT_FOUND
            yield from emit_whole(text)
            yield finish(text, [], False, 0.0, "web", [], used_web=True, research_job_id=job.id)
            return
        ctx = AnswerContext(question=question, language=language, company=company, mode="web", web_pages=pages, history=history, products=products)
        sources = [
            Source(n=i, source_type="web", source_id=job.id, title=p["title"], section=None, url=p["url"], verified=False,
                   updated_at=p["retrieved_at"], version=None, product_id=None, snippet=p["excerpt"][:280], official=p["official"])
            for i, p in enumerate(pages, start=1)
        ]
        yield {"type": "sources", "sources": [s.as_dict() for s in sources]}
        state: dict = {}
        parts: list[str] = []
        for tok in _stream_generation(ctx, provider_name, model, temperature, state):
            parts.append(tok)
            yield {"type": "token", "content": tok}
        content = "".join(parts).strip() or WEB_NOT_FOUND
        yield finish(content, sources, False, 0.0, state.get("provider", "web"), [], used_web=True, research_job_id=job.id)
        return

    # ---- cache (first-turn questions only) ----
    cache_key = _answer_cache_key(question, user, language, provider_name)
    if not history and not regenerate:
        cached = get_cache().get_json(cache_key)
        if cached:
            yield {"type": "sources", "sources": cached["sources"]}
            yield from emit_whole(cached["content"])
            src_objs = [Source(**s) for s in cached["sources"]]
            yield finish(cached["content"], src_objs, True, cached["confidence"], f"{cached['provider']} (cached)", cached["related"])
            return

    # ---- retrieval ----
    top_k = int(get_setting(db, "retrieval_top_k") or 6)
    min_score = float(get_setting(db, "answer_min_score") or 0.3)
    chunks = hybrid_search(db, retrieval_query, user, top_k=top_k, product_ids=product_ids or None)
    confidence = max((c.relevance for c in chunks), default=0.0)
    if not chunks or confidence < min_score:
        yield from emit_whole(NOT_FOUND)
        yield finish(NOT_FOUND, [], False, confidence, "none", [])
        return
    # Only keep chunks reasonably close to the best one
    chunks = [c for c in chunks if c.relevance >= max(min_score * 0.6, confidence - 0.35)]
    sources, chunk_source = build_sources(chunks)
    ctx = AnswerContext(
        question=question, language=language, company=company, chunks=chunks, sources=sources, chunk_source=chunk_source,
        products=products, history=history,
    )
    yield {"type": "sources", "sources": [s.as_dict() for s in sources]}

    state = {}
    parts = []
    for tok in _stream_generation(ctx, provider_name, model, temperature, state):
        parts.append(tok)
        yield {"type": "token", "content": tok}
    content = "".join(parts).strip()
    answered = bool(content) and NOT_FOUND[:40] not in content
    if not content:
        content = NOT_FOUND
        yield from emit_whole(content)
    # Only show sources that the answer actually cites (fall back to all if the model didn't cite)
    cited = [s for s in sources if f"[{s.n}]" in content]
    final_sources = cited or (sources if answered else [])
    related = _related_questions(db, products, question) if answered else []
    done = finish(content, final_sources, answered, confidence, state.get("provider", provider_name), related)
    if answered and not history:
        ttl = int(get_setting(db, "answer_cache_ttl_seconds") or 3600)
        get_cache().set_json(
            cache_key,
            {"content": content, "sources": done["sources"], "confidence": done["confidence"], "provider": done["provider"], "related": related},
            ttl,
        )
    yield done
