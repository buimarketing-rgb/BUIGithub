from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300), default="New conversation")
    language: Mapped[str] = mapped_column(String(20), default="en-US")
    is_voice: Mapped[bool] = mapped_column(Boolean, default=False)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.id"
    )


class Message(TimestampMixin, Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSONB, default=list)
    related_questions: Mapped[list] = mapped_column(JSONB, default=list)
    # Analytics fields (assistant messages)
    question: Mapped[str | None] = mapped_column(Text)
    answered: Mapped[bool | None] = mapped_column(Boolean, index=True)
    confidence: Mapped[float | None] = mapped_column(Float)
    used_web: Mapped[bool] = mapped_column(Boolean, default=False)
    product_ids: Mapped[list] = mapped_column(JSONB, default=list)
    provider: Mapped[str | None] = mapped_column(String(50))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)  # admin handled this knowledge gap

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Feedback(TimestampMixin, Base):
    __tablename__ = "feedback"
    __table_args__ = (UniqueConstraint("message_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    helpful: Mapped[bool] = mapped_column(Boolean)
    comment: Mapped[str | None] = mapped_column(Text)
