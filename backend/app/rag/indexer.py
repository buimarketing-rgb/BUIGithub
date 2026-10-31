"""Keeps the unified retrieval index (document_chunks) in sync with company knowledge.

Every create / update / delete of a document, product, FAQ or approved research finding calls
one of these functions so answers always reflect the latest approved information.
"""
import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.cache import invalidate_answer_cache
from app.core.config import get_settings
from app.models import FAQ, DocumentChunk, KnowledgeDocument, Product, ResearchFinding, SystemSetting
from app.rag.chunking import chunk_text
from app.rag.embeddings import embed_texts, get_embedder
from app.rag.safety import sanitize_source_text

log = logging.getLogger(__name__)

INDEXED_PRODUCT_STATUSES = ("verified", "needs_review")


def _embedding_input(title: str, section: str | None, text: str) -> str:
    head = f"{title} - {section}" if section else title
    return f"{head}\n{text}"


def remove_source(db: Session, source_type: str, source_id: int) -> None:
    db.execute(delete(DocumentChunk).where(DocumentChunk.source_type == source_type, DocumentChunk.source_id == source_id))
    invalidate_answer_cache()


def _store(db: Session, rows: list[dict]) -> int:
    if not rows:
        return 0
    vectors = embed_texts([_embedding_input(r["title"], r.get("section"), r["content"]) for r in rows])
    for r, v in zip(rows, vectors):
        db.add(DocumentChunk(embedding=v, **r))
    return len(rows)


def index_document(db: Session, doc: KnowledgeDocument) -> int:
    remove_source(db, "document", doc.id)
    if doc.status != "published" or not doc.content:
        doc.chunk_count = 0
        return 0
    s = get_settings()
    rows = []
    for i, ch in enumerate(chunk_text(sanitize_source_text(doc.content), s.chunk_size, s.chunk_overlap)):
        rows.append(
            dict(
                source_type="document",
                source_id=doc.id,
                document_id=doc.id,
                product_id=doc.product_id,
                chunk_index=i,
                title=doc.title,
                section=ch.section,
                category=doc.category,
                visibility=doc.visibility,
                verified=doc.source_type != "research",
                source_url=doc.source_url,
                version=doc.current_version,
                content=ch.text,
                meta={"filename": doc.original_filename, "source_type": doc.source_type},
                source_updated_at=doc.updated_at,
            )
        )
    doc.chunk_count = _store(db, rows)
    return doc.chunk_count


def _bullets(items: list) -> str:
    return "\n".join(f"- {i}" for i in items if str(i).strip())


def product_sections(p: Product) -> list[tuple[str, str, str]]:
    """(section, category, text) tuples describing a product."""
    ident = f"Product: {p.name}" + (f" | Brand: {p.brand}" if p.brand else "") + (f" | Model: {p.model_number}" if p.model_number else "")
    if p.category:
        ident += f" | Category: {p.category.name}"
    sections: list[tuple[str, str, str]] = []
    overview = ident + ("\n\n" + p.description if p.description else "")
    if p.applications:
        overview += "\n\nApplications:\n" + _bullets(p.applications)
    sections.append(("Overview", "product_catalogue", overview))
    if p.specifications:
        specs = "\n".join(f"- {k}: {v}" for k, v in p.specifications.items())
        sections.append(("Specifications", "product_specifications", f"{ident}\n\nTechnical specifications:\n{specs}"))
    if p.features:
        sections.append(("Features", "product_features", f"{ident}\n\nFeatures and advantages:\n{_bullets(p.features)}"))
    if p.compatibility:
        sections.append(("Compatibility", "technical_information", f"{ident}\n\nCompatible with:\n{_bullets(p.compatibility)}"))
    if p.accessories:
        sections.append(("Accessories", "product_catalogue", f"{ident}\n\nAvailable accessories:\n{_bullets(p.accessories)}"))
    for attr, label, cat in (
        ("pricing", "Pricing", "pricing_information"),
        ("warranty", "Warranty", "warranty_information"),
        ("installation", "Installation", "installation_guides"),
        ("maintenance", "Maintenance", "user_manuals"),
        ("troubleshooting", "Troubleshooting", "troubleshooting"),
    ):
        val = getattr(p, attr)
        if val:
            sections.append((label, cat, f"{ident}\n\n{label}:\n{val}"))
    return sections


def index_product(db: Session, p: Product) -> int:
    remove_source(db, "product", p.id)
    if p.status not in INDEXED_PRODUCT_STATUSES:
        return 0
    s = get_settings()
    rows = []
    idx = 0
    for section, category, text in product_sections(p):
        for ch in chunk_text(sanitize_source_text(text), s.chunk_size * 2, s.chunk_overlap):
            rows.append(
                dict(
                    source_type="product",
                    source_id=p.id,
                    product_id=p.id,
                    chunk_index=idx,
                    title=p.name,
                    section=section,
                    category=category,
                    visibility="internal",
                    verified=p.status == "verified",
                    source_url=(p.source_urls or [None])[0],
                    version=p.version,
                    content=ch.text,
                    meta={"status": p.status, "model_number": p.model_number, "brand": p.brand},
                    source_updated_at=p.updated_at,
                )
            )
            idx += 1
    return _store(db, rows)


def index_faq(db: Session, faq: FAQ) -> int:
    remove_source(db, "faq", faq.id)
    if faq.status != "published":
        return 0
    text = sanitize_source_text(f"Question: {faq.question}\nAnswer: {faq.answer}")
    return _store(
        db,
        [
            dict(
                source_type="faq",
                source_id=faq.id,
                product_id=faq.product_id,
                chunk_index=0,
                title=f"FAQ: {faq.question[:300]}",
                section="FAQ",
                category=faq.category or "faq",
                visibility=faq.visibility,
                verified=True,
                version=1,
                content=text,
                meta={"question": faq.question},
                source_updated_at=faq.updated_at,
            )
        ],
    )


def index_research_finding(db: Session, f: ResearchFinding) -> int:
    """Approved research is searchable but always labelled as third-party (verified=False)."""
    remove_source(db, "research", f.id)
    if f.status != "approved":
        return 0
    label = f"{f.key}: {f.value}" if f.key else f.value
    src = f.source
    product_name = None
    if f.product_id:
        prod = db.get(Product, f.product_id)
        product_name = prod.name if prod else None
    title = f"Approved research{' - ' + product_name if product_name else ''}"
    text = sanitize_source_text((f"Product: {product_name}\n" if product_name else "") + f"{f.category.title()}: {label}")
    return _store(
        db,
        [
            dict(
                source_type="research",
                source_id=f.id,
                product_id=f.product_id,
                chunk_index=0,
                title=title,
                section=f.category,
                category="technical_information",
                visibility="internal",
                verified=False,
                source_url=src.url if src else None,
                version=1,
                content=text,
                meta={"retrieved_at": src.retrieved_at.isoformat() if src and src.retrieved_at else None, "domain": src.domain if src else None},
                source_updated_at=f.reviewed_at,
            )
        ],
    )


SIGNATURE_KEY = "_embedding_signature"


def reindex_all(db: Session) -> dict[str, int]:
    db.execute(delete(DocumentChunk))
    counts = {"documents": 0, "products": 0, "faqs": 0, "research": 0}
    for doc in db.scalars(select(KnowledgeDocument)):
        index_document(db, doc)
        counts["documents"] += 1
    for p in db.scalars(select(Product)):
        index_product(db, p)
        counts["products"] += 1
    for f in db.scalars(select(FAQ)):
        index_faq(db, f)
        counts["faqs"] += 1
    for rf in db.scalars(select(ResearchFinding).where(ResearchFinding.status == "approved")):
        index_research_finding(db, rf)
        counts["research"] += 1
    _save_signature(db)
    invalidate_answer_cache()
    return counts


def _save_signature(db: Session) -> None:
    row = db.get(SystemSetting, SIGNATURE_KEY)
    if row is None:
        row = SystemSetting(key=SIGNATURE_KEY, description="Embedding model used to build the index (internal)")
        db.add(row)
    row.value = get_embedder().name


def ensure_index_consistency(db: Session) -> bool:
    """Rebuilds the index if the embedding model changed since it was built. Returns True if rebuilt."""
    row = db.get(SystemSetting, SIGNATURE_KEY)
    current = get_embedder().name
    if row is not None and row.value == current:
        return False
    has_chunks = db.scalar(select(DocumentChunk.id).limit(1)) is not None
    if row is None and not has_chunks:
        _save_signature(db)
        db.commit()
        return False
    log.warning("Embedding model changed (%s -> %s); rebuilding knowledge index", row.value if row else None, current)
    reindex_all(db)
    db.commit()
    return True
