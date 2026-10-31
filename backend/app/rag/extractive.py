"""No-LLM answer composer.

Builds answers *only* by selecting and structuring text that already exists in the verified
knowledge base, so it cannot hallucinate. Used when no LLM is configured or reachable, and as an
automatic fallback when the configured provider fails.
"""
import re
from collections.abc import Iterator

from app.models import Product
from app.rag.embeddings import tokenize
from app.rag.prompt import AnswerContext

_SENT_RE = re.compile(r"(?<=[.!?])\s+|\n+")

INTENTS: list[tuple[str, tuple[str, ...]]] = [
    ("compare", ("compare", "comparison", "difference", "differences", "versus", " vs", "better", "differ")),
    ("warranty", ("warranty", "guarantee", "guaranty")),
    ("installation", ("install", "installation", "mount", "setup", "set up", "fitting")),
    ("troubleshooting", ("problem", "issue", "error", "troubleshoot", "fault", "not working", "fix", "leak", "fail")),
    ("accessories", ("accessor", "add-on", "spare", "parts")),
    ("compatibility", ("compatible", "compatibility", "work with", "fit with", "support")),
    ("features", ("feature", "advantage", "benefit", "why choose", "highlight")),
    ("pricing", ("price", "cost", "pricing", "how much", "mrp", "rate")),
    ("maintenance", ("maintenance", "maintain", "clean", "service", "servicing")),
    ("specifications", ("spec", "specification", "dimension", "technical data", "technical detail")),
]

FIELD_FOR_INTENT = {
    "warranty": ("warranty", "Warranty"),
    "installation": ("installation", "Installation"),
    "troubleshooting": ("troubleshooting", "Troubleshooting"),
    "pricing": ("pricing", "Pricing"),
    "maintenance": ("maintenance", "Maintenance"),
}


def detect_intents(question: str, products: list[Product] | None = None) -> list[str]:
    q = f" {question.lower()} "
    for p in products or []:  # product names must not trigger intents ("power" in "PowerGuard")
        for name in (p.name, p.model_number, p.brand):
            if name:
                q = q.replace(name.lower(), " ")
    return [name for name, kws in INTENTS if any(re.search(r"(?<![a-z])" + re.escape(k.strip()), q) for k in kws)]


def _section_source(ctx: AnswerContext, product_id: int, section: str) -> int | None:
    for s in ctx.sources:
        if s.source_type == "product" and s.source_id == product_id and (s.section or "").lower() == section.lower():
            return s.n
    for s in ctx.sources:
        if s.product_id == product_id:
            return s.n
    return None


def _best_sentences(ctx: AnswerContext, limit: int = 4, product_id: int | None = None, exclude_terms: set[str] | None = None) -> list[tuple[str, int]]:
    q_terms = set(tokenize(ctx.question)) - (exclude_terms or set())
    scored: list[tuple[float, str, int]] = []
    seen: set[str] = set()
    for rank, c in enumerate(ctx.chunks):
        if product_id is not None and c.product_id not in (product_id, None):
            continue
        n = ctx.chunk_source[c.id]
        for sent in _SENT_RE.split(c.content):
            sent = sent.strip(" -•\t")
            if sent.startswith("Answer: "):
                sent = sent[8:]
            if len(sent) < 25 or sent.lower() in seen or sent.startswith(("Product: ", "Question: ", "#", "[Page", "[Sheet")):
                continue
            terms = set(tokenize(sent))
            overlap = len(q_terms & terms)
            if not overlap:
                continue
            score = overlap / (len(q_terms) or 1) + c.relevance * 0.5 - rank * 0.02
            scored.append((score, sent, n))
            seen.add(sent.lower())
    scored.sort(key=lambda x: -x[0])
    return [(s, n) for _, s, n in scored[:limit]]


def _relevant_specs(p: Product, question: str, intents: list[str]) -> list[tuple[str, str]]:
    specs = list((p.specifications or {}).items())
    if not specs:
        return []
    if "specifications" in intents and not any(i in intents for i in ("warranty", "installation", "troubleshooting")):
        q_terms = set(tokenize(question)) - {"spec", "specification", "product", "technical"}
        if p.name:
            q_terms -= set(tokenize(p.name)) | set(tokenize(p.model_number or ""))
        matched = [(k, v) for k, v in specs if q_terms & set(tokenize(f"{k} {v}"))]
        return matched or specs[:15]
    q_terms = set(tokenize(question)) - set(tokenize(f"{p.name} {p.model_number or ''} {p.brand or ''}"))
    if not q_terms:
        return []
    # Without an explicit spec question, a spec must cover most of the question's terms
    return [(k, v) for k, v in specs if len(q_terms & set(tokenize(k))) >= max(1, (len(q_terms) + 1) // 2)][:6]


def _product_answer(ctx: AnswerContext, p: Product, intents: list[str]) -> tuple[list[str], set[int]]:
    out = [f"**Product Name:** {p.name}"]
    if p.model_number:
        out.append(f"**Model:** {p.model_number}")
    if p.brand:
        out.append(f"**Brand:** {p.brand}")
    answer_lines: list[str] = []
    cited: set[int] = set()

    for intent in intents:
        if intent in FIELD_FOR_INTENT:
            attr, label = FIELD_FOR_INTENT[intent]
            val = getattr(p, attr)
            if val:
                n = _section_source(ctx, p.id, label)
                cited.add(n) if n else None
                answer_lines.append(f"{val.strip()} {f'[{n}]' if n else ''}".strip())
        elif intent in ("features", "accessories", "compatibility"):
            items = getattr(p, intent) or []
            if items:
                n = _section_source(ctx, p.id, intent.capitalize())
                cited.add(n) if n else None
                label = {"features": "Key features", "accessories": "Available accessories", "compatibility": "Compatible with"}[intent]
                answer_lines.append(f"{label}{f' [{n}]' if n else ''}:\n" + "\n".join(f"- {i}" for i in items))

    name_terms = set(tokenize(f"{p.name} {p.model_number or ''} {p.brand or ''}"))
    specs = _relevant_specs(p, ctx.question, intents)
    if not answer_lines and not specs:
        for sent, n in _best_sentences(ctx, 4, p.id, name_terms):
            answer_lines.append(f"{sent} [{n}]")
            cited.add(n)
    if not answer_lines and not specs and p.description:
        n = _section_source(ctx, p.id, "Overview")
        cited.add(n) if n else None
        answer_lines.append(f"{p.description} {f'[{n}]' if n else ''}".strip())
    if answer_lines:
        out.append("**Answer:**\n" + "\n\n".join(answer_lines))
    if specs:
        n = _section_source(ctx, p.id, "Specifications")
        cited.add(n) if n else None
        out.append(f"**Important Specifications:**{f' [{n}]' if n else ''}\n" + "\n".join(f"- **{k}:** {v}" for k, v in specs))
    # Supporting information from other documents / FAQs about this product
    extra = [(s, n) for s, n in _best_sentences(ctx, 3, p.id, name_terms) if n not in cited and not any(s in line for line in answer_lines)]
    other_sources = {n for _, n in extra if any(src.n == n and src.source_type != "product" for src in ctx.sources)}
    extra = [(s, n) for s, n in extra if n in other_sources]
    if extra:
        out.append("**Additional Information:**\n" + "\n".join(f"- {s} [{n}]" for s, n in extra))
        cited |= {n for _, n in extra}
    if p.status == "needs_review":
        out.append("> ⚠️ This product's information is currently marked **needs review** by an administrator.")
    return out, cited


def _comparison(ctx: AnswerContext, products: list[Product]) -> list[str]:
    keys: list[str] = []
    for p in products:
        for k in (p.specifications or {}):
            if k not in keys:
                keys.append(k)
    header = "| Specification | " + " | ".join(p.name for p in products) + " |"
    sep = "|---|" + "---|" * len(products)
    rows = [header, sep]
    if any(p.model_number for p in products):
        rows.append("| Model | " + " | ".join(p.model_number or "—" for p in products) + " |")
    for k in keys:
        rows.append(f"| {k} | " + " | ".join(str((p.specifications or {}).get(k, "—")) for p in products) + " |")
    if any(p.warranty for p in products):
        rows.append("| Warranty | " + " | ".join((p.warranty or "—").split(".")[0] for p in products) + " |")
    out = [f"**Comparison: {' vs '.join(p.name for p in products)}**", "\n".join(rows)]
    for p in products:
        if p.features:
            n = _section_source(ctx, p.id, "Features")
            out.append(f"**{p.name} – key features**{f' [{n}]' if n else ''}\n" + "\n".join(f"- {f}" for f in p.features[:6]))
    cites = sorted({n for p in products if (n := _section_source(ctx, p.id, "Specifications"))})
    if cites:
        out.append("**Source:** " + " ".join(f"[{n}]" for n in cites))
    return out


def compose(ctx: AnswerContext) -> str:
    if ctx.mode == "web":
        return _compose_web(ctx)
    intents = detect_intents(ctx.question, ctx.products)
    parts: list[str]
    if len(ctx.products) >= 2:
        parts = _comparison(ctx, ctx.products[:4])
    elif len(ctx.products) == 1:
        parts, cited = _product_answer(ctx, ctx.products[0], intents)
        srcs = sorted(cited) or sorted({ctx.chunk_source[c.id] for c in ctx.chunks if c.product_id == ctx.products[0].id})[:1]
        if srcs:
            parts.append("**Source:** " + " ".join(f"[{n}]" for n in srcs))
        upd = max((s.updated_at for s in ctx.sources if s.product_id == ctx.products[0].id and s.updated_at), default=None)
        if upd:
            parts.append(f"**Last Updated:** {upd}")
    else:
        sents = _best_sentences(ctx, 5)
        if not sents:
            return ""
        parts = ["Here is what I found in the BUI knowledge base:", "\n".join(f"- {s} [{n}]" for s, n in sents)]
    if any(not s.verified for s in ctx.sources if f"[{s.n}]" in "\n".join(parts)):
        parts.append("> ℹ️ Items citing *approved research* come from third-party sources, not company-verified documents.")
    return "\n\n".join(parts)


def _compose_web(ctx: AnswerContext) -> str:
    parts = [
        f"**Online research - unverified.** The following was found on public websites and has not been approved by {ctx.company}."
    ]
    q_terms = set(tokenize(ctx.question))
    for i, page in enumerate(ctx.web_pages, start=1):
        sents = []
        for s in _SENT_RE.split(page["excerpt"]):
            s = s.strip()
            if 25 <= len(s) <= 400 and q_terms & set(tokenize(s)):
                sents.append(s)
            if len(sents) >= 3:
                break
        if sents:
            tag = " *(official source)*" if page.get("official") else ""
            parts.append(f"**{page['title']}**{tag} [{i}]\n" + "\n".join(f"- {s}" for s in sents))
    if len(parts) == 1:
        return ""
    parts.append("Please ask an administrator to review and approve this information before relying on it.")
    return "\n\n".join(parts)


def stream_compose(ctx: AnswerContext) -> Iterator[str]:
    text = compose(ctx)
    # Emit in small pieces so the UI streams consistently with LLM providers
    for piece in re.findall(r"\S+\s*|\s+", text):
        yield piece
