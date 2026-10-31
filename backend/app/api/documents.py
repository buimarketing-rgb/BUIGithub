"""Knowledge documents: manual entries and uploaded files (PDF, DOCX, XLSX, CSV, TXT, MD), with
versioning. Every change re-indexes automatically (in the background for files)."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import require_admin, require_member
from app.core.security import sign_file_url
from app.models import DocumentVersion, KnowledgeDocument, Product, User
from app.models.knowledge import DOCUMENT_STATUSES, KNOWLEDGE_CATEGORIES, VISIBILITY
from app.rag.indexer import index_document, remove_source
from app.rag.parsers import UnsupportedFile, validate_upload
from app.schemas.common import DocumentDetail, DocumentIn, DocumentOut, DocumentUpdate, DocumentVersionOut, Page
from app.services import storage
from app.services.audit import audit
from app.workers.jobs import process_document, submit

router = APIRouter(prefix="/documents", tags=["documents"])


def _validate_meta(category: str | None, status: str | None, visibility: str | None) -> None:
    if category is not None and category not in KNOWLEDGE_CATEGORIES:
        raise HTTPException(400, f"Invalid category. Use one of: {', '.join(KNOWLEDGE_CATEGORIES)}")
    if status is not None and status not in DOCUMENT_STATUSES:
        raise HTTPException(400, "Invalid status")
    if visibility is not None and visibility not in VISIBILITY:
        raise HTTPException(400, "Invalid visibility")


def _out(db: Session, d: KnowledgeDocument, detail: bool = False):
    product_name = db.scalar(select(Product.name).where(Product.id == d.product_id)) if d.product_id else None
    base = DocumentOut.model_validate(d).model_copy(update={"product_name": product_name, "content_preview": (d.content or "")[:300] or None})
    if not detail:
        return base
    versions = [
        DocumentVersionOut.model_validate(v).model_copy(update={"download_url": sign_file_url("docver", v.id) if v.file_path else None})
        for v in d.versions
    ]
    current = next((v for v in d.versions if v.version == d.current_version), None)
    return DocumentDetail(
        **base.model_dump(), content=d.content, versions=versions,
        download_url=sign_file_url("docver", current.id) if current and current.file_path else None,
    )


def _visible(db: Session, doc_id: int, user: User) -> KnowledgeDocument:
    d = db.get(KnowledgeDocument, doc_id)
    if not d:
        raise HTTPException(404, "Document not found")
    if not user.has_role("admin") and (d.status != "published" or d.visibility != "internal"):
        raise HTTPException(404, "Document not found")
    return d


@router.get("/categories")
def categories(_: User = Depends(require_member)):
    return [{"value": c, "label": c.replace("_", " ").title().replace("Faq", "FAQ")} for c in KNOWLEDGE_CATEGORIES]


@router.get("", response_model=Page[DocumentOut])
def list_documents(
    q: str | None = None, category: str | None = None, status: str | None = None, product_id: int | None = None,
    source_type: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_member), db: Session = Depends(get_db),
):
    stmt = select(KnowledgeDocument)
    if not user.has_role("admin"):
        stmt = stmt.where(KnowledgeDocument.status == "published", KnowledgeDocument.visibility == "internal")
    elif status:
        stmt = stmt.where(KnowledgeDocument.status == status)
    if q:
        stmt = stmt.where(or_(KnowledgeDocument.title.ilike(f"%{q}%"), KnowledgeDocument.content.ilike(f"%{q}%"), KnowledgeDocument.original_filename.ilike(f"%{q}%")))
    if category:
        stmt = stmt.where(KnowledgeDocument.category == category)
    if product_id:
        stmt = stmt.where(KnowledgeDocument.product_id == product_id)
    if source_type:
        stmt = stmt.where(KnowledgeDocument.source_type == source_type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    docs = db.scalars(stmt.order_by(KnowledgeDocument.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=[_out(db, d) for d in docs], total=total, page=page, page_size=page_size)


@router.get("/{doc_id}", response_model=DocumentDetail)
def get_document(doc_id: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    return _out(db, _visible(db, doc_id, user), detail=True)


@router.post("", response_model=DocumentDetail, status_code=201)
def create_entry(body: DocumentIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Manually entered knowledge (company information, policies, notes...)."""
    _validate_meta(body.category, body.status, body.visibility)
    d = KnowledgeDocument(
        title=body.title.strip(), category=body.category, source_type="url" if body.source_url else "manual", source_url=body.source_url,
        product_id=body.product_id, tags=body.tags, status=body.status, visibility=body.visibility, content=body.content,
        current_version=1, processing_status="processing", created_by_id=user.id, updated_by_id=user.id,
    )
    db.add(d)
    db.flush()
    d.versions.append(DocumentVersion(version=1, title=d.title, content=d.content, change_note=body.change_note or "Created", created_by_id=user.id))
    index_document(db, d)
    d.processing_status = "ready"
    audit(db, user, "document.create", "document", d.id, f"Created knowledge entry '{d.title}'", request=request)
    db.commit()
    return _out(db, d, detail=True)


@router.post("/upload", response_model=DocumentDetail, status_code=201)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    category: str = Form("other"),
    product_id: int | None = Form(None),
    tags: str | None = Form(None),
    status: str = Form("published"),
    visibility: str = Form("internal"),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _validate_meta(category, status, visibility)
    data = await file.read()
    try:
        vf = validate_upload(file.filename or "", data, get_settings().max_upload_mb * 1024 * 1024, allow_images=False)
    except UnsupportedFile as exc:
        raise HTTPException(400, str(exc))
    path = storage.save_bytes("documents", vf.extension, data)
    name = (file.filename or "document")[:255]
    d = KnowledgeDocument(
        title=(title or name.rsplit(".", 1)[0]).strip()[:300], category=category, source_type="file", product_id=product_id or None,
        tags=[t.strip() for t in (tags or "").split(",") if t.strip()], status=status, visibility=visibility,
        file_path=path, original_filename=name, content_type=vf.content_type, file_size=len(data), current_version=1,
        processing_status="pending", created_by_id=user.id, updated_by_id=user.id,
    )
    db.add(d)
    db.flush()
    d.versions.append(DocumentVersion(version=1, title=d.title, file_path=path, original_filename=name, content_type=vf.content_type, file_size=len(data), change_note="Uploaded", created_by_id=user.id))
    audit(db, user, "document.upload", "document", d.id, f"Uploaded '{name}'", {"size": len(data)}, request=request)
    db.commit()
    submit(process_document, d.id)
    db.refresh(d)
    return _out(db, d, detail=True)


@router.post("/{doc_id}/versions", response_model=DocumentDetail, status_code=201)
async def upload_new_version(
    doc_id: int, request: Request, file: UploadFile = File(...), change_note: str | None = Form(None),
    user: User = Depends(require_admin), db: Session = Depends(get_db),
):
    d = db.get(KnowledgeDocument, doc_id)
    if not d:
        raise HTTPException(404, "Document not found")
    data = await file.read()
    try:
        vf = validate_upload(file.filename or "", data, get_settings().max_upload_mb * 1024 * 1024, allow_images=False)
    except UnsupportedFile as exc:
        raise HTTPException(400, str(exc))
    path = storage.save_bytes("documents", vf.extension, data)
    name = (file.filename or "document")[:255]
    d.current_version += 1
    d.file_path, d.original_filename, d.content_type, d.file_size = path, name, vf.content_type, len(data)
    d.source_type = "file"
    d.processing_status = "pending"
    d.updated_by_id = user.id
    d.versions.append(DocumentVersion(version=d.current_version, title=d.title, file_path=path, original_filename=name, content_type=vf.content_type, file_size=len(data), change_note=change_note or "New version uploaded", created_by_id=user.id))
    audit(db, user, "document.new_version", "document", d.id, f"Uploaded version {d.current_version} of '{d.title}'", request=request)
    db.commit()
    submit(process_document, d.id)
    db.refresh(d)
    return _out(db, d, detail=True)


@router.patch("/{doc_id}", response_model=DocumentDetail)
def update_document(doc_id: int, body: DocumentUpdate, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    d = db.get(KnowledgeDocument, doc_id)
    if not d:
        raise HTTPException(404, "Document not found")
    _validate_meta(body.category, body.status, body.visibility)
    changes = body.model_dump(exclude_unset=True, exclude={"change_note", "clear_product"})
    for k in ("title", "category", "tags", "status", "visibility", "source_url"):
        if k in changes and changes[k] is not None:
            setattr(d, k, changes[k])
    if body.product_id is not None:
        d.product_id = body.product_id
    if body.clear_product:
        d.product_id = None
    if body.content is not None and body.content != d.content:
        d.current_version += 1
        d.content = body.content
        if d.source_type == "file":
            d.source_type = "manual"
            d.file_path = None
        d.versions.append(DocumentVersion(version=d.current_version, title=d.title, content=body.content, change_note=body.change_note or "Content edited", created_by_id=user.id))
    d.updated_by_id = user.id
    db.flush()
    index_document(db, d)
    d.processing_status = "ready" if d.content else d.processing_status
    audit(db, user, "document.update", "document", d.id, f"Updated '{d.title}'", {"fields": sorted(changes)}, request=request)
    db.commit()
    return _out(db, d, detail=True)


@router.post("/{doc_id}/versions/{version}/restore", response_model=DocumentDetail)
def restore_document_version(doc_id: int, version: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    d = db.get(KnowledgeDocument, doc_id)
    v = next((x for x in (d.versions if d else []) if x.version == version), None)
    if not d or not v:
        raise HTTPException(404, "Version not found")
    d.current_version += 1
    d.title, d.content, d.file_path, d.original_filename, d.content_type, d.file_size = v.title, v.content, v.file_path, v.original_filename, v.content_type, v.file_size
    d.versions.append(DocumentVersion(version=d.current_version, title=v.title, content=v.content, file_path=v.file_path, original_filename=v.original_filename, content_type=v.content_type, file_size=v.file_size, change_note=f"Restored version {version}", created_by_id=user.id))
    db.flush()
    index_document(db, d)
    audit(db, user, "document.restore", "document", d.id, f"Restored '{d.title}' to v{version}", request=request)
    db.commit()
    return _out(db, d, detail=True)


@router.post("/{doc_id}/reprocess", response_model=DocumentDetail)
def reprocess(doc_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    d = db.get(KnowledgeDocument, doc_id)
    if not d:
        raise HTTPException(404, "Document not found")
    d.processing_status = "pending"
    db.commit()
    submit(process_document, d.id)
    db.refresh(d)
    return _out(db, d, detail=True)


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    d = db.get(KnowledgeDocument, doc_id)
    if not d:
        raise HTTPException(404, "Document not found")
    remove_source(db, "document", d.id)
    for v in d.versions:
        storage.delete(v.file_path)
    audit(db, user, "document.delete", "document", d.id, f"Deleted '{d.title}'", request=request)
    db.delete(d)
    db.commit()
