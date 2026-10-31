from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import Date, cast, func, select, update
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin, require_member
from app.models import (
    FAQ, Conversation, DocumentChunk, Feedback, KnowledgeDocument, Message, Product, ResearchFinding, ResearchJob, User,
)
from app.rag.indexer import index_faq
from app.schemas.common import UnansweredToFAQ
from app.services.audit import audit

router = APIRouter(prefix="/analytics", tags=["analytics"])

_qnorm = func.lower(func.trim(Message.question))


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _top_questions(db: Session, since: datetime, limit: int, answered: bool | None = None, include_resolved: bool = True):
    stmt = select(_qnorm.label("q"), func.count().label("n"), func.max(Message.created_at).label("last"), func.max(Message.id).label("mid")).where(
        Message.role == "assistant", Message.question.is_not(None), Message.created_at >= since, Message.provider != "clarification"
    )
    if answered is not None:
        stmt = stmt.where(Message.answered.is_(answered), Message.used_web.is_(False))
    if not include_resolved:
        stmt = stmt.where(Message.resolved.is_(False))
    rows = db.execute(stmt.group_by("q").order_by(func.count().desc(), func.max(Message.created_at).desc()).limit(limit)).all()
    return [{"question": r.q, "count": r.n, "last_asked": r.last, "message_id": r.mid} for r in rows]


@router.get("/dashboard")
def dashboard(user: User = Depends(require_member), db: Session = Depends(get_db)):
    month = _since(30)
    total_q = db.scalar(select(func.count()).select_from(Message).where(Message.role == "assistant")) or 0
    q30 = db.scalar(select(func.count()).select_from(Message).where(Message.role == "assistant", Message.created_at >= month)) or 0
    answered30 = db.scalar(select(func.count()).select_from(Message).where(Message.role == "assistant", Message.created_at >= month, Message.answered.is_(True))) or 0
    docs_total = db.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0
    docs_ready = db.scalar(select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.processing_status == "ready")) or 0
    docs_failed = db.scalar(select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.processing_status == "failed")) or 0
    needs_review = db.scalar(select(func.count()).select_from(Product).where(Product.status == "needs_review")) or 0
    pending_findings = db.scalar(select(func.count()).select_from(ResearchFinding).where(ResearchFinding.status == "pending")) or 0
    stale_cutoff = _since(180)
    stale_products = db.scalar(select(func.count()).select_from(Product).where(Product.status == "verified", Product.updated_at < stale_cutoff)) or 0
    helpful = db.scalar(select(func.count()).select_from(Feedback).where(Feedback.helpful.is_(True))) or 0
    feedback_total = db.scalar(select(func.count()).select_from(Feedback)) or 0
    unanswered_open = db.scalar(select(func.count(func.distinct(_qnorm))).where(Message.role == "assistant", Message.answered.is_(False), Message.used_web.is_(False), Message.resolved.is_(False))) or 0

    # Health score: weighted mix of processing success, answer rate, review backlog and freshness
    processing = docs_ready / docs_total if docs_total else 1.0
    answer_rate = answered30 / q30 if q30 else 1.0
    products_total = db.scalar(select(func.count()).select_from(Product).where(Product.status != "archived")) or 0
    freshness = 1 - (stale_products / products_total) if products_total else 1.0
    review = 1 - min(1.0, (needs_review + docs_failed) / max(products_total + docs_total, 1))
    health = round(100 * (0.3 * processing + 0.35 * answer_rate + 0.2 * freshness + 0.15 * review))

    recent: list[dict] = []
    for p in db.scalars(select(Product).where(Product.status != "archived").order_by(Product.updated_at.desc()).limit(6)):
        recent.append({"type": "product", "id": p.id, "title": p.name, "updated_at": p.updated_at, "detail": f"v{p.version} · {p.status}"})
    doc_stmt = select(KnowledgeDocument).order_by(KnowledgeDocument.updated_at.desc()).limit(6)
    if not user.has_role("admin"):
        doc_stmt = doc_stmt.where(KnowledgeDocument.status == "published", KnowledgeDocument.visibility == "internal")
    for d in db.scalars(doc_stmt):
        recent.append({"type": "document", "id": d.id, "title": d.title, "updated_at": d.updated_at, "detail": d.category.replace("_", " ")})
    for f in db.scalars(select(FAQ).where(FAQ.status == "published").order_by(FAQ.updated_at.desc()).limit(4)):
        recent.append({"type": "faq", "id": f.id, "title": f.question, "updated_at": f.updated_at, "detail": "FAQ"})
    recent.sort(key=lambda r: r["updated_at"], reverse=True)

    return {
        "totals": {
            "products": products_total,
            "documents": docs_total,
            "faqs": db.scalar(select(func.count()).select_from(FAQ).where(FAQ.status == "published")) or 0,
            "team_members": db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0,
            "questions": total_q,
            "questions_30d": q30,
            "research_jobs": db.scalar(select(func.count()).select_from(ResearchJob)) or 0,
            "unanswered_open": unanswered_open,
        },
        "recently_updated": recent[:10],
        "most_asked": _top_questions(db, month, 6),
        "unanswered": _top_questions(db, _since(90), 6, answered=False, include_resolved=False) if user.has_role("admin") else [],
        "health": {
            "score": health,
            "answer_rate": round(answer_rate * 100, 1),
            "documents_ready": docs_ready,
            "documents_failed": docs_failed,
            "products_needing_review": needs_review,
            "stale_products": stale_products,
            "pending_research_findings": pending_findings,
            "indexed_chunks": db.scalar(select(func.count()).select_from(DocumentChunk)) or 0,
            "helpful_rate": round(100 * helpful / feedback_total, 1) if feedback_total else None,
        },
    }


@router.get("/overview")
def overview(days: int = Query(30, ge=1, le=365), _: User = Depends(require_admin), db: Session = Depends(get_db)):
    since = _since(days)
    day = cast(Message.created_at, Date)
    series = db.execute(
        select(day.label("d"), func.count().label("n"), func.count().filter(Message.answered.is_(True)).label("ok"))
        .where(Message.role == "assistant", Message.created_at >= since).group_by("d").order_by("d")
    ).all()
    rday = cast(ResearchJob.created_at, Date)
    research = db.execute(select(rday.label("d"), func.count()).where(ResearchJob.created_at >= since).group_by("d").order_by("d")).all()
    stats = db.execute(
        select(
            func.count(), func.count().filter(Message.answered.is_(True)), func.avg(Message.latency_ms), func.avg(Message.confidence),
            func.count().filter(Message.used_web.is_(True)),
        ).where(Message.role == "assistant", Message.created_at >= since)
    ).one()
    # Most searched products: unnest product_ids JSON arrays
    prod_rows = db.execute(
        select(func.jsonb_array_elements_text(Message.product_ids).label("pid"), func.count()).where(Message.role == "assistant", Message.created_at >= since).group_by("pid").order_by(func.count().desc()).limit(8)
    ).all()
    names = dict(db.execute(select(Product.id, Product.name).where(Product.id.in_([int(r[0]) for r in prod_rows]))).all()) if prod_rows else {}
    fb = db.execute(select(func.count().filter(Feedback.helpful.is_(True)), func.count().filter(Feedback.helpful.is_(False))).where(Feedback.created_at >= since)).one()
    low_conf = db.execute(
        select(Message.id, Message.question, Message.confidence, Message.created_at).where(
            Message.role == "assistant", Message.answered.is_(True), Message.confidence < 0.45, Message.created_at >= since, Message.provider != "clarification"
        ).order_by(Message.confidence.asc()).limit(10)
    ).all()
    return {
        "days": days,
        "questions_per_day": [{"date": r.d.isoformat(), "questions": r.n, "answered": r.ok} for r in series],
        "research_per_day": [{"date": r[0].isoformat(), "jobs": r[1]} for r in research],
        "totals": {
            "questions": stats[0], "answered": stats[1], "answer_rate": round(100 * stats[1] / stats[0], 1) if stats[0] else None,
            "avg_latency_ms": int(stats[2]) if stats[2] else None, "avg_confidence": round(float(stats[3]), 3) if stats[3] else None,
            "web_answers": stats[4], "helpful": fb[0], "not_helpful": fb[1],
            "active_users": db.scalar(select(func.count(func.distinct(Conversation.user_id))).where(Conversation.updated_at >= since)) or 0,
        },
        "top_questions": _top_questions(db, since, 10),
        "top_products": [{"product_id": int(r[0]), "name": names.get(int(r[0]), f"#{r[0]}"), "count": r[1]} for r in prod_rows],
        "low_confidence": [{"message_id": r.id, "question": r.question, "confidence": r.confidence, "created_at": r.created_at} for r in low_conf],
    }


@router.get("/unanswered")
def unanswered(days: int = Query(90, ge=1, le=365), include_resolved: bool = False, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return _top_questions(db, _since(days), 100, answered=False, include_resolved=include_resolved)


@router.get("/feedback")
def negative_feedback(limit: int = Query(30, le=100), _: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Feedback, Message, User.email).join(Message, Feedback.message_id == Message.id).join(User, Feedback.user_id == User.id)
        .order_by(Feedback.created_at.desc()).limit(limit)
    ).all()
    return [
        {"id": f.id, "helpful": f.helpful, "comment": f.comment, "question": m.question, "answer": m.content[:600], "user": email, "created_at": f.created_at, "message_id": m.id}
        for f, m, email in rows
    ]


class ResolveIn(BaseModel):
    question: str


@router.post("/unanswered/resolve", status_code=204)
def resolve(body: ResolveIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    db.execute(update(Message).where(_qnorm == body.question.strip().lower(), Message.answered.is_(False)).values(resolved=True))
    audit(db, user, "analytics.resolve_gap", "message", None, f"Resolved knowledge gap: {body.question[:150]}", request=request)
    db.commit()


@router.post("/unanswered/to-faq", status_code=201)
def to_faq(body: UnansweredToFAQ, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if body.product_id and not db.get(Product, body.product_id):
        raise HTTPException(404, "Product not found")
    f = FAQ(question=body.question.strip(), answer=body.answer.strip(), product_id=body.product_id, category=body.category, origin="unanswered_question", created_by_id=user.id, updated_by_id=user.id)
    db.add(f)
    db.flush()
    index_faq(db, f)
    db.execute(update(Message).where(_qnorm == body.question.strip().lower(), Message.answered.is_(False)).values(resolved=True))
    audit(db, user, "faq.create_from_gap", "faq", f.id, f.question[:200], request=request)
    db.commit()
    return {"id": f.id}
