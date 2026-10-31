from sqlalchemy.orm import Session

from app.models import Product, ProductVersion, User

SNAPSHOT_FIELDS = (
    "name", "brand", "model_number", "category_id", "description", "specifications", "features", "applications",
    "compatibility", "accessories", "pricing", "warranty", "installation", "maintenance", "troubleshooting",
    "source_urls", "tags", "status",
)


def product_snapshot(p: Product) -> dict:
    return {f: getattr(p, f) for f in SNAPSHOT_FIELDS}


def snapshot_product(db: Session, p: Product, user: User | None, note: str | None) -> ProductVersion:
    v = ProductVersion(product_id=p.id, version=p.version, snapshot=product_snapshot(p), change_note=note, changed_by_id=user.id if user else None)
    db.add(v)
    return v


def diff_snapshots(old: dict, new: dict) -> list[str]:
    return [f for f in SNAPSHOT_FIELDS if old.get(f) != new.get(f)]
