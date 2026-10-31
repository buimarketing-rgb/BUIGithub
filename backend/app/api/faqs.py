from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin, require_member
from app.models import FAQ, Product, User
from app.rag.indexer import index_faq, remove_source
from app.schemas.common import FAQIn, FAQOut, Page
from app.services.audit import audit

router = APIRouter(prefix="/faqs", tags=["faqs"])


def faq_out(db: Session, f: FAQ) -> FAQOut:
    name = db.scalar(select(Product.name).where(Product.id == f.product_id)) if f.product_id else None
    return FAQOut.model_validate(f).model_copy(update={"product_name": name})


@router.get("", response_model=Page[FAQOut])
def list_faqs(
    q: str | None = None, product_id: int | None = None, status: str | None = None, category: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(require_member), db: Session = Depends(get_db),
):
    stmt = select(FAQ)
    if not user.has_role("admin"):
        stmt = stmt.where(FAQ.status == "published", FAQ.visibility == "internal")
    elif status:
        stmt = stmt.where(FAQ.status == status)
    if q:
        stmt = stmt.where(or_(FAQ.question.ilike(f"%{q}%"), FAQ.answer.ilike(f"%{q}%")))
    if product_id:
        stmt = stmt.where(FAQ.product_id == product_id)
    if category:
        stmt = stmt.where(FAQ.category == category)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(FAQ.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=[faq_out(db, f) for f in rows], total=total, page=page, page_size=page_size)


def _validate(body: FAQIn) -> None:
    if body.status not in ("draft", "published", "archived") or body.visibility not in ("internal", "restricted"):
        raise HTTPException(400, "Invalid status or visibility")


@router.post("", response_model=FAQOut, status_code=201)
def create_faq(body: FAQIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    _validate(body)
    f = FAQ(**body.model_dump(), created_by_id=user.id, updated_by_id=user.id)
    db.add(f)
    db.flush()
    index_faq(db, f)
    audit(db, user, "faq.create", "faq", f.id, f.question[:200], request=request)
    db.commit()
    return faq_out(db, f)


@router.put("/{faq_id}", response_model=FAQOut)
def update_faq(faq_id: int, body: FAQIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    _validate(body)
    f = db.get(FAQ, faq_id)
    if not f:
        raise HTTPException(404, "FAQ not found")
    for k, v in body.model_dump().items():
        setattr(f, k, v)
    f.updated_by_id = user.id
    db.flush()
    index_faq(db, f)
    audit(db, user, "faq.update", "faq", f.id, f.question[:200], request=request)
    db.commit()
    return faq_out(db, f)


@router.delete("/{faq_id}", status_code=204)
def delete_faq(faq_id: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    f = db.get(FAQ, faq_id)
    if not f:
        raise HTTPException(404, "FAQ not found")
    remove_source(db, "faq", f.id)
    audit(db, user, "faq.delete", "faq", f.id, f.question[:200], request=request)
    db.delete(f)
    db.commit()
