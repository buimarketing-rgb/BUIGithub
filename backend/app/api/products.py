from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import require_admin, require_member
from app.core.security import sign_file_url
from app.models import FAQ, KnowledgeDocument, Product, ProductCategory, ProductImage, ProductVersion, User
from app.rag.indexer import index_product, remove_source
from app.rag.parsers import UnsupportedFile, validate_upload
from app.schemas.common import (
    CategoryIn, CategoryOut, Page, ProductImageOut, ProductIn, ProductListItem, ProductOut, ProductVersionOut,
)
from app.services import storage
from app.services.audit import audit
from app.services.products import SNAPSHOT_FIELDS, diff_snapshots, product_snapshot, snapshot_product

router = APIRouter(tags=["products"])


# ---------------- categories ----------------
@router.get("/categories", response_model=list[CategoryOut])
def list_categories(_: User = Depends(require_member), db: Session = Depends(get_db)):
    counts = dict(db.execute(select(Product.category_id, func.count()).where(Product.status != "archived").group_by(Product.category_id)).all())
    return [
        CategoryOut(id=c.id, name=c.name, description=c.description, parent_id=c.parent_id, product_count=counts.get(c.id, 0))
        for c in db.scalars(select(ProductCategory).order_by(ProductCategory.name))
    ]


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(body: CategoryIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.scalar(select(ProductCategory).where(func.lower(ProductCategory.name) == body.name.strip().lower())):
        raise HTTPException(409, "Category already exists")
    c = ProductCategory(name=body.name.strip(), description=body.description, parent_id=body.parent_id)
    db.add(c)
    db.flush()
    audit(db, user, "category.create", "category", c.id, c.name, request=request)
    db.commit()
    return CategoryOut.model_validate(c)


@router.put("/categories/{cid}", response_model=CategoryOut)
def update_category(cid: int, body: CategoryIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    c = db.get(ProductCategory, cid)
    if not c:
        raise HTTPException(404, "Category not found")
    c.name, c.description, c.parent_id = body.name.strip(), body.description, body.parent_id
    audit(db, user, "category.update", "category", c.id, c.name, request=request)
    db.commit()
    for p in db.scalars(select(Product).where(Product.category_id == cid)):
        index_product(db, p)  # category name is part of the indexed text
    db.commit()
    return CategoryOut.model_validate(c)


@router.delete("/categories/{cid}", status_code=204)
def delete_category(cid: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    c = db.get(ProductCategory, cid)
    if not c:
        raise HTTPException(404, "Category not found")
    audit(db, user, "category.delete", "category", c.id, c.name, request=request)
    db.delete(c)
    db.commit()


# ---------------- products ----------------
def _image_out(img: ProductImage) -> ProductImageOut:
    return ProductImageOut(id=img.id, original_name=img.original_name, caption=img.caption, url=sign_file_url("image", img.id, 6 * 3600))


def product_out(db: Session, p: Product) -> ProductOut:
    data = {f: getattr(p, f) for f in SNAPSHOT_FIELDS}
    return ProductOut(
        **data, id=p.id, version=p.version, created_at=p.created_at, updated_at=p.updated_at,
        category_name=p.category.name if p.category else None, images=[_image_out(i) for i in p.images],
        document_count=db.scalar(select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.product_id == p.id)) or 0,
        faq_count=db.scalar(select(func.count()).select_from(FAQ).where(FAQ.product_id == p.id)) or 0,
    )


def _get_visible(db: Session, pid: int, user: User) -> Product:
    p = db.get(Product, pid)
    if not p or (not user.has_role("admin") and p.status in ("draft", "archived")):
        raise HTTPException(404, "Product not found")
    return p


@router.get("/products", response_model=Page[ProductListItem])
def list_products(
    q: str | None = None, category_id: int | None = None, status: str | None = None, brand: str | None = None,
    sort: str = "updated", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_member), db: Session = Depends(get_db),
):
    stmt = select(Product)
    if not user.has_role("admin"):
        stmt = stmt.where(Product.status.in_(("verified", "needs_review")))
    elif status:
        stmt = stmt.where(Product.status == status)
    else:
        stmt = stmt.where(Product.status != "archived")
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Product.name.ilike(like), Product.model_number.ilike(like), Product.brand.ilike(like), Product.description.ilike(like)))
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if brand:
        stmt = stmt.where(Product.brand.ilike(brand))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    order = {"name": Product.name.asc(), "updated": Product.updated_at.desc(), "created": Product.created_at.desc()}.get(sort, Product.updated_at.desc())
    items = db.scalars(stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)).unique().all()
    return Page(
        items=[ProductListItem.model_validate(p).model_copy(update={"category_name": p.category.name if p.category else None}) for p in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/products/brands", response_model=list[str])
def list_brands(_: User = Depends(require_member), db: Session = Depends(get_db)):
    return [b for b in db.scalars(select(Product.brand).where(Product.brand.is_not(None)).distinct().order_by(Product.brand))]


@router.get("/products/{pid}", response_model=ProductOut)
def get_product(pid: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    return product_out(db, _get_visible(db, pid, user))


@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(body: ProductIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    data = body.model_dump(exclude={"change_note"})
    p = Product(**data, version=1, created_by_id=user.id, updated_by_id=user.id)
    db.add(p)
    db.flush()
    snapshot_product(db, p, user, body.change_note or "Created")
    db.refresh(p)
    index_product(db, p)
    audit(db, user, "product.create", "product", p.id, f"Created product {p.name}", request=request)
    db.commit()
    return product_out(db, p)


@router.put("/products/{pid}", response_model=ProductOut)
def update_product(pid: int, body: ProductIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found")
    before = product_snapshot(p)
    for k, v in body.model_dump(exclude={"change_note"}).items():
        setattr(p, k, v)
    changed = diff_snapshots(before, product_snapshot(p))
    if changed:
        p.version += 1
        p.updated_by_id = user.id
        db.flush()
        snapshot_product(db, p, user, body.change_note or f"Updated {', '.join(changed)}")
        db.refresh(p)
        index_product(db, p)
        audit(db, user, "product.update", "product", p.id, f"Updated {p.name} to v{p.version}", {"fields": changed}, request=request)
    db.commit()
    return product_out(db, p)


@router.post("/products/{pid}/archive", response_model=ProductOut)
def archive_product(pid: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found")
    p.status = "archived"
    p.version += 1
    db.flush()
    snapshot_product(db, p, user, "Archived")
    index_product(db, p)  # removes it from the index
    audit(db, user, "product.archive", "product", p.id, f"Archived {p.name}", request=request)
    db.commit()
    return product_out(db, p)


@router.delete("/products/{pid}", status_code=204)
def delete_product(pid: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found")
    remove_source(db, "product", p.id)
    for img in p.images:
        storage.delete(img.file_path)
    audit(db, user, "product.delete", "product", p.id, f"Deleted {p.name}", {"snapshot": product_snapshot(p)}, request=request)
    db.delete(p)
    db.commit()


@router.get("/products/{pid}/versions", response_model=list[ProductVersionOut])
def product_versions(pid: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.scalars(select(ProductVersion).where(ProductVersion.product_id == pid).order_by(ProductVersion.version.desc())).all()


@router.post("/products/{pid}/versions/{version}/restore", response_model=ProductOut)
def restore_version(pid: int, version: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    v = db.scalar(select(ProductVersion).where(ProductVersion.product_id == pid, ProductVersion.version == version))
    if not p or not v:
        raise HTTPException(404, "Version not found")
    for k, val in v.snapshot.items():
        setattr(p, k, val)
    p.version += 1
    p.updated_by_id = user.id
    db.flush()
    snapshot_product(db, p, user, f"Restored version {version}")
    db.refresh(p)
    index_product(db, p)
    audit(db, user, "product.restore", "product", p.id, f"Restored {p.name} to v{version}", request=request)
    db.commit()
    return product_out(db, p)


@router.post("/products/{pid}/images", response_model=ProductImageOut, status_code=201)
async def upload_image(
    pid: int, request: Request, file: UploadFile = File(...), caption: str | None = Form(None),
    user: User = Depends(require_admin), db: Session = Depends(get_db),
):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found")
    data = await file.read()
    try:
        vf = validate_upload(file.filename or "", data, get_settings().max_upload_mb * 1024 * 1024, allow_documents=False)
    except UnsupportedFile as exc:
        raise HTTPException(400, str(exc))
    img = ProductImage(product_id=p.id, file_path=storage.save_bytes("images", vf.extension, data), original_name=(file.filename or "image")[:255], caption=caption, content_type=vf.content_type)
    db.add(img)
    db.flush()
    audit(db, user, "product.image_upload", "product", p.id, f"Uploaded image {img.original_name}", request=request)
    db.commit()
    return _image_out(img)


@router.delete("/products/{pid}/images/{image_id}", status_code=204)
def delete_image(pid: int, image_id: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    img = db.get(ProductImage, image_id)
    if not img or img.product_id != pid:
        raise HTTPException(404, "Image not found")
    storage.delete(img.file_path)
    audit(db, user, "product.image_delete", "product", pid, f"Deleted image {img.original_name}", request=request)
    db.delete(img)
    db.commit()
