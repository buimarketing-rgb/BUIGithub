from fastapi import Request
from sqlalchemy.orm import Session

from app.models.system import AuditLog
from app.models.user import User


def audit(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: int | str | None = None,
    summary: str | None = None,
    details: dict | None = None,
    request: Request | None = None,
) -> None:
    """Adds an audit entry to the current transaction (caller commits)."""
    ip = None
    if request is not None:
        fwd = request.headers.get("x-forwarded-for")
        ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            user_email=user.email if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            summary=summary,
            details=details or {},
            ip_address=ip,
        )
    )
