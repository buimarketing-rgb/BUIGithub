import re
from datetime import datetime
from typing import Annotated, Generic, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+'-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")


def _email(v: str) -> str:
    """Accepts internal domains such as name@company.local (pydantic's EmailStr rejects them)."""
    v = v.strip().lower()
    if len(v) > 254 or not _EMAIL_RE.match(v):
        raise ValueError("Enter a valid e-mail address")
    return v


EmailStr = Annotated[str, AfterValidator(_email)]

T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


# ---------- auth / users ----------
class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserOut(ORM):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    preferred_language: str
    last_login_at: datetime | None
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=200)
    preferred_language: str | None = Field(None, max_length=20)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=200)


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=10, max_length=200)


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    role: str = "team_member"
    password: str = Field(min_length=10, max_length=200)


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=200)
    role: str | None = None
    is_active: bool | None = None


# ---------- products ----------
class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    parent_id: int | None = None


class CategoryOut(ORM):
    id: int
    name: str
    description: str | None
    parent_id: int | None
    product_count: int = 0


def _clean_list(v):
    if v is None:
        return []
    return [str(x).strip() for x in v if str(x).strip()]


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    brand: str | None = Field(None, max_length=150)
    model_number: str | None = Field(None, max_length=150)
    category_id: int | None = None
    description: str | None = None
    specifications: dict[str, str] = Field(default_factory=dict)
    features: list[str] = Field(default_factory=list)
    applications: list[str] = Field(default_factory=list)
    compatibility: list[str] = Field(default_factory=list)
    accessories: list[str] = Field(default_factory=list)
    pricing: str | None = None
    warranty: str | None = None
    installation: str | None = None
    maintenance: str | None = None
    troubleshooting: str | None = None
    source_urls: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: str = "verified"

    _lists = field_validator("features", "applications", "compatibility", "accessories", "source_urls", "tags", mode="before")(_clean_list)

    @field_validator("specifications", mode="before")
    @classmethod
    def _specs(cls, v):
        return {str(k).strip(): str(val).strip() for k, val in (v or {}).items() if str(k).strip()}

    @field_validator("status")
    @classmethod
    def _status(cls, v):
        if v not in ("draft", "verified", "needs_review", "archived"):
            raise ValueError("invalid status")
        return v


class ProductIn(ProductBase):
    change_note: str | None = None


class ProductImageOut(ORM):
    id: int
    original_name: str
    caption: str | None
    url: str = ""


class ProductOut(ProductBase, ORM):
    id: int
    category_name: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime
    images: list[ProductImageOut] = []
    document_count: int = 0
    faq_count: int = 0


class ProductListItem(ORM):
    id: int
    name: str
    brand: str | None
    model_number: str | None
    category_id: int | None
    category_name: str | None = None
    status: str
    version: int
    updated_at: datetime
    description: str | None


class ProductVersionOut(ORM):
    id: int
    version: int
    change_note: str | None
    changed_by_id: int | None
    created_at: datetime
    snapshot: dict


# ---------- documents ----------
class DocumentIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    category: str = "other"
    content: str = Field(min_length=1)
    product_id: int | None = None
    tags: list[str] = Field(default_factory=list)
    status: str = "published"
    visibility: str = "internal"
    source_url: str | None = None
    change_note: str | None = None


class DocumentUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    category: str | None = None
    product_id: int | None = None
    tags: list[str] | None = None
    status: str | None = None
    visibility: str | None = None
    content: str | None = None  # when set, creates a new version
    source_url: str | None = None
    change_note: str | None = None
    clear_product: bool = False


class DocumentVersionOut(ORM):
    id: int
    version: int
    title: str
    original_filename: str | None
    file_size: int | None
    change_note: str | None
    created_by_id: int | None
    created_at: datetime
    download_url: str | None = None


class DocumentOut(ORM):
    id: int
    title: str
    category: str
    source_type: str
    source_url: str | None
    product_id: int | None
    product_name: str | None = None
    tags: list[str]
    status: str
    visibility: str
    processing_status: str
    processing_error: str | None
    current_version: int
    original_filename: str | None
    content_type: str | None
    file_size: int | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime
    content_preview: str | None = None


class DocumentDetail(DocumentOut):
    content: str | None = None
    versions: list[DocumentVersionOut] = []
    download_url: str | None = None


# ---------- FAQs ----------
class FAQIn(BaseModel):
    question: str = Field(min_length=3)
    answer: str = Field(min_length=1)
    product_id: int | None = None
    category: str = "faq"
    tags: list[str] = Field(default_factory=list)
    status: str = "published"
    visibility: str = "internal"


class FAQOut(ORM):
    id: int
    question: str
    answer: str
    product_id: int | None
    product_name: str | None = None
    category: str
    tags: list[str]
    status: str
    visibility: str
    origin: str
    created_at: datetime
    updated_at: datetime


# ---------- chat ----------
class ChatIn(BaseModel):
    message: str = Field("", max_length=4000)
    conversation_id: int | None = None
    language: str = Field("en-US", max_length=20)
    web: bool = False
    regenerate: bool = False
    is_voice: bool = False


class FeedbackIn(BaseModel):
    helpful: bool
    comment: str | None = Field(None, max_length=2000)


class MessageOut(ORM):
    id: int
    role: str
    content: str
    sources: list
    related_questions: list
    answered: bool | None
    confidence: float | None
    used_web: bool
    provider: str | None
    latency_ms: int | None
    created_at: datetime
    feedback: bool | None = None


class ConversationOut(ORM):
    id: int
    title: str
    language: str
    is_voice: bool
    created_at: datetime
    updated_at: datetime
    snippet: str | None = None


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=300)


# ---------- research ----------
class ResearchJobIn(BaseModel):
    query: str | None = Field(None, max_length=500)
    url: str | None = Field(None, max_length=1000)
    product_id: int | None = None
    schedule_hours: int | None = Field(None, ge=1, le=24 * 90)


class ResearchJobUpdate(BaseModel):
    schedule_hours: int | None = Field(None, ge=1, le=24 * 90)
    clear_schedule: bool = False


class ResearchSourceOut(ORM):
    id: int
    url: str
    domain: str
    title: str | None
    snippet: str | None
    is_official: bool
    robots_allowed: bool
    fetch_status: str
    http_status: int | None
    retrieved_at: datetime | None


class ResearchFindingOut(ORM):
    id: int
    job_id: int
    source_id: int | None
    product_id: int | None
    category: str
    key: str | None
    value: str
    status: str
    is_duplicate: bool
    has_conflict: bool
    conflict_with: str | None
    confidence: float
    reviewed_at: datetime | None
    review_note: str | None
    source_url: str | None = None
    source_domain: str | None = None
    source_official: bool = False
    retrieved_at: datetime | None = None


class ResearchJobOut(ORM):
    id: int
    query: str | None
    url: str | None
    product_id: int | None
    product_name: str | None = None
    status: str
    error: str | None
    origin: str
    schedule_hours: int | None
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    finding_counts: dict = {}


class ResearchJobDetail(ResearchJobOut):
    log: list
    sources: list[ResearchSourceOut]
    findings: list[ResearchFindingOut]


class FindingReview(BaseModel):
    finding_ids: list[int] = Field(min_length=1)
    action: str  # approve | reject
    apply_to_product: bool = True
    replace_conflicts: bool = False
    note: str | None = None


class SettingsUpdate(BaseModel):
    values: dict


class UnansweredToFAQ(BaseModel):
    question: str = Field(min_length=3)
    answer: str = Field(min_length=1)
    product_id: int | None = None
    category: str = "faq"
