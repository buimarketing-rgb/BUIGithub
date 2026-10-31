from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.core.database import Base
from app.models.base import TimestampMixin

KNOWLEDGE_CATEGORIES = (
    "company_information",
    "product_catalogue",
    "product_specifications",
    "product_features",
    "product_comparisons",
    "pricing_information",
    "warranty_information",
    "installation_guides",
    "user_manuals",
    "troubleshooting",
    "faq",
    "sales_information",
    "technical_information",
    "company_policies",
    "other",
)
DOCUMENT_STATUSES = ("draft", "published", "archived")
VISIBILITY = ("internal", "restricted")  # restricted = admins only
PROCESSING_STATUSES = ("pending", "processing", "ready", "failed")


class KnowledgeDocument(TimestampMixin, Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    category: Mapped[str] = mapped_column(String(50), index=True, default="other")
    source_type: Mapped[str] = mapped_column(String(20), default="manual")  # manual | file | url | research
    source_url: Mapped[str | None] = mapped_column(String(1000))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), index=True)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default="published", index=True)
    visibility: Mapped[str] = mapped_column(String(20), default="internal")
    processing_status: Mapped[str] = mapped_column(String(20), default="pending")
    processing_error: Mapped[str | None] = mapped_column(Text)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[str | None] = mapped_column(Text)  # extracted/entered text of the current version
    file_path: Mapped[str | None] = mapped_column(String(500))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(150))
    file_size: Mapped[int | None] = mapped_column(Integer)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentVersion.version.desc()"
    )


class DocumentVersion(TimestampMixin, Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(String(500))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(150))
    file_size: Mapped[int | None] = mapped_column(Integer)
    change_note: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    document: Mapped[KnowledgeDocument] = relationship(back_populates="versions")


class DocumentChunk(Base):
    """Unified retrieval index: chunks from documents, products, FAQs and approved research."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_chunks_source", "source_type", "source_id"),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(20))  # document | product | faq | research
    source_id: Mapped[int] = mapped_column(Integer)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(400))
    section: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50), default="other", index=True)
    visibility: Mapped[str] = mapped_column(String(20), default="internal")
    verified: Mapped[bool] = mapped_column(default=True)  # False for approved third-party research
    source_url: Mapped[str | None] = mapped_column(String(1000))
    version: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    embedding = mapped_column(Vector(get_settings().embedding_dim))
    tsv = mapped_column(TSVECTOR, Computed("to_tsvector('english', coalesce(title,'') || ' ' || content)", persisted=True))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FAQ(TimestampMixin, Base):
    __tablename__ = "faqs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), index=True)
    category: Mapped[str] = mapped_column(String(50), default="faq")
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default="published", index=True)
    visibility: Mapped[str] = mapped_column(String(20), default="internal")
    origin: Mapped[str] = mapped_column(String(30), default="manual")  # manual | unanswered_question | research
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
