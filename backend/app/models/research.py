from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

FINDING_STATUSES = ("pending", "approved", "rejected")


class ResearchJob(TimestampMixin, Base):
    __tablename__ = "research_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query: Mapped[str | None] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(String(1000))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued | running | completed | failed
    error: Mapped[str | None] = mapped_column(Text)
    log: Mapped[list] = mapped_column(JSONB, default=list)
    origin: Mapped[str] = mapped_column(String(20), default="admin")  # admin | chat | schedule
    schedule_hours: Mapped[int | None] = mapped_column(Integer)  # re-run interval; None = manual only
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    sources: Mapped[list["ResearchSource"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    findings: Mapped[list["ResearchFinding"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class ResearchSource(TimestampMixin, Base):
    __tablename__ = "research_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("research_jobs.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(1000))
    domain: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str | None] = mapped_column(String(500))
    snippet: Mapped[str | None] = mapped_column(Text)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)
    robots_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    fetch_status: Mapped[str] = mapped_column(String(30), default="pending")  # fetched | blocked_robots | error | skipped
    http_status: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    extracted_text: Mapped[str | None] = mapped_column(Text)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job: Mapped[ResearchJob] = relationship(back_populates="sources")


class ResearchFinding(TimestampMixin, Base):
    __tablename__ = "research_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("research_jobs.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("research_sources.id", ondelete="SET NULL"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), index=True)
    category: Mapped[str] = mapped_column(String(50))  # specification | feature | warranty | installation | description | faq | other
    key: Mapped[str | None] = mapped_column(String(300))
    value: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    has_conflict: Mapped[bool] = mapped_column(Boolean, default=False)
    conflict_with: Mapped[str | None] = mapped_column(Text)  # the verified value it disagrees with
    confidence: Mapped[float] = mapped_column(default=0.5)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)

    job: Mapped[ResearchJob] = relationship(back_populates="findings")
    source: Mapped[ResearchSource | None] = relationship(lazy="joined")
