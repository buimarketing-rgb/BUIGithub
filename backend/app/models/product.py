from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

PRODUCT_STATUSES = ("draft", "verified", "needs_review", "archived")


class ProductCategory(TimestampMixin, Base):
    __tablename__ = "product_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("product_categories.id", ondelete="SET NULL"))


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    brand: Mapped[str | None] = mapped_column(String(150), index=True)
    model_number: Mapped[str | None] = mapped_column(String(150), index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("product_categories.id", ondelete="SET NULL"), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    specifications: Mapped[dict] = mapped_column(JSON, default=dict)  # JSON (not JSONB) keeps key order
    features: Mapped[list] = mapped_column(JSONB, default=list)
    applications: Mapped[list] = mapped_column(JSONB, default=list)
    compatibility: Mapped[list] = mapped_column(JSONB, default=list)
    accessories: Mapped[list] = mapped_column(JSONB, default=list)
    pricing: Mapped[str | None] = mapped_column(Text)
    warranty: Mapped[str | None] = mapped_column(Text)
    installation: Mapped[str | None] = mapped_column(Text)
    maintenance: Mapped[str | None] = mapped_column(Text)
    troubleshooting: Mapped[str | None] = mapped_column(Text)
    source_urls: Mapped[list] = mapped_column(JSONB, default=list)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(30), default="verified", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    category: Mapped[ProductCategory | None] = relationship(lazy="joined")
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductImage.id"
    )


class ProductImage(TimestampMixin, Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    original_name: Mapped[str] = mapped_column(String(255))
    caption: Mapped[str | None] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(100))

    product: Mapped[Product] = relationship(back_populates="images")


class ProductVersion(TimestampMixin, Base):
    """Immutable snapshot of a product each time it changes."""

    __tablename__ = "product_versions"
    __table_args__ = (UniqueConstraint("product_id", "version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSONB)
    change_note: Mapped[str | None] = mapped_column(Text)
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
