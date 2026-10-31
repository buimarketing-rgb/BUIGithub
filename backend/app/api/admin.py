"""System settings, health, audit log, knowledge search tester, re-indexing and export."""
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.cache import get_cache, invalidate_answer_cache
from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import require_admin, require_member, require_super_admin
from app.llm.providers import build_provider
from app.models import FAQ, AuditLog, DocumentChunk, KnowledgeDocument, Product, ProductCategory, User
from app.rag.embeddings import get_embedder
from app.rag.indexer import reindex_all
from app.rag.retriever import detect_products, hybrid_search
from app.research.search import get_search_provider
from app.schemas.common import SettingsUpdate
from app.services.audit import audit
from app.services.products import product_snapshot
from app.services.system_settings import all_settings, defaults, get_setting, set_setting

router = APIRouter(tags=["admin"])


@router.get("/settings")
def get_settings_view(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return all_settings(db)


@router.get("/settings/public")
def public_settings(_: User = Depends(require_member), db: Session = Depends(get_db)):
    s = get_settings()
    return {
        "company_name": get_setting(db, "company_name"),
        "default_language": get_setting(db, "default_language"),
        "web_research_enabled": bool(get_setting(db, "web_research_enabled")),
        "team_can_research_from_chat": bool(get_setting(db, "team_can_research_from_chat")),
        "whisper_enabled": s.whisper_enabled,
        "max_upload_mb": s.max_upload_mb,
    }


@router.put("/settings")
def update_settings(body: SettingsUpdate, request: Request, user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    known = defaults()
    for key, value in body.values.items():
        if key not in known:
            raise HTTPException(400, f"Unknown setting '{key}'")
        if key == "llm_provider" and value not in ("ollama", "openai", "extractive"):
            raise HTTPException(400, "llm_provider must be ollama, openai or extractive")
        if key in ("answer_min_score", "llm_temperature") and not (0 <= float(value) <= 1.5):
            raise HTTPException(400, f"{key} out of range")
        if key == "official_domains" and not isinstance(value, list):
            raise HTTPException(400, "official_domains must be a list")
        set_setting(db, key, value, user.id)
    audit(db, user, "settings.update", "system_settings", None, "Updated settings", {"keys": sorted(body.values)}, request=request)
    db.commit()
    invalidate_answer_cache()
    return all_settings(db)


@router.get("/system/health")
def health_detail(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    out: dict = {}
    t = time.monotonic()
    try:
        db.execute(text("SELECT 1"))
        out["database"] = {"ok": True, "detail": f"{int((time.monotonic() - t) * 1000)} ms"}
    except Exception as exc:
        out["database"] = {"ok": False, "detail": str(exc)}
    out["cache"] = {"ok": True, "detail": get_cache().backend}
    emb = get_embedder()
    out["embeddings"] = {"ok": True, "detail": emb.name, "fallback": emb.name.startswith("hash")}
    provider_name = get_setting(db, "llm_provider")
    provider = build_provider(provider_name, get_setting(db, "llm_model"))
    out["llm"] = {"provider": provider_name, **(provider.health() if provider else {"ok": True, "detail": "Extractive mode (no LLM): answers are composed directly from verified sources"})}
    sp = get_search_provider()
    out["search"] = {"ok": sp is not None, "detail": sp.name if sp else "not configured"}
    if sp is not None and sp.name == "searxng":
        try:
            import httpx

            r = httpx.get(get_settings().searxng_url, timeout=3)
            out["search"]["ok"] = r.status_code < 500
        except Exception as exc:
            out["search"] = {"ok": False, "detail": f"SearXNG unreachable: {exc}"}
    out["voice"] = {"browser": True, "whisper": get_settings().whisper_enabled}
    return out


@router.get("/audit-logs")
def audit_logs(
    action: str | None = None, entity_type: str | None = None, user_id: int | None = None, q: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), _: User = Depends(require_admin), db: Session = Depends(get_db),
):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"{action}%"))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if q:
        stmt = stmt.where(AuditLog.summary.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [
            {"id": r.id, "created_at": r.created_at, "user_email": r.user_email, "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id, "summary": r.summary, "details": r.details, "ip_address": r.ip_address}
            for r in rows
        ],
        "total": total, "page": page, "page_size": page_size,
    }


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(8, ge=1, le=30)
    categories: list[str] | None = None


@router.post("/knowledge/search")
def knowledge_search(body: SearchIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    """Hybrid semantic + keyword search over the knowledge base (used by global search and the admin tester)."""
    match = detect_products(db, body.query)
    t = time.monotonic()
    chunks = hybrid_search(db, body.query, user, top_k=body.top_k, product_ids=[p.id for p in match.products] or None, categories=body.categories)
    return {
        "took_ms": int((time.monotonic() - t) * 1000),
        "detected_products": [{"id": p.id, "name": p.name} for p in match.products],
        "ambiguous_products": [{"id": p.id, "name": p.name} for p in match.ambiguous],
        "results": [
            {
                "chunk_id": c.id, "source_type": c.source_type, "source_id": c.source_id, "product_id": c.product_id, "title": c.title,
                "section": c.section, "category": c.category, "verified": c.verified, "source_url": c.source_url, "version": c.version,
                "content": c.content, "relevance": round(c.relevance, 3), "vector_score": round(c.vector_score, 3), "keyword_rank": round(c.keyword_rank, 4),
                "updated_at": c.source_updated_at,
            }
            for c in chunks
        ],
    }


@router.get("/knowledge/stats")
def knowledge_stats(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    by_type = dict(db.execute(select(DocumentChunk.source_type, func.count()).group_by(DocumentChunk.source_type)).all())
    by_cat = dict(db.execute(select(DocumentChunk.category, func.count()).group_by(DocumentChunk.category)).all())
    return {"chunks_by_source": by_type, "chunks_by_category": by_cat, "embedding_model": get_embedder().name}


@router.post("/knowledge/reindex")
def reindex(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    t = time.monotonic()
    counts = reindex_all(db)
    audit(db, user, "knowledge.reindex", "knowledge", None, "Rebuilt knowledge index", counts, request=request)
    db.commit()
    return {"counts": counts, "took_ms": int((time.monotonic() - t) * 1000)}


@router.get("/admin/export")
def export_knowledge(request: Request, user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    """JSON export of company knowledge (complements the full pg_dump backup scripts)."""
    data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "categories": [{"id": c.id, "name": c.name, "description": c.description} for c in db.scalars(select(ProductCategory))],
        "products": [{"id": p.id, "version": p.version, **product_snapshot(p)} for p in db.scalars(select(Product))],
        "documents": [
            {"id": d.id, "title": d.title, "category": d.category, "status": d.status, "visibility": d.visibility, "product_id": d.product_id, "tags": d.tags, "version": d.current_version, "content": d.content, "original_filename": d.original_filename}
            for d in db.scalars(select(KnowledgeDocument))
        ],
        "faqs": [{"id": f.id, "question": f.question, "answer": f.answer, "product_id": f.product_id, "status": f.status} for f in db.scalars(select(FAQ))],
    }
    audit(db, user, "knowledge.export", "knowledge", None, "Exported knowledge JSON", request=request)
    db.commit()
    return JSONResponse(data, headers={"Content-Disposition": f'attachment; filename="bui-knowledge-{datetime.now():%Y%m%d}.json"'})
