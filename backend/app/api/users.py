"""Team management. Admins manage team members; only Super Admins manage administrators."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.api.auth import create_reset_token, user_out
from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import require_admin
from app.core.security import hash_password, validate_password_strength
from app.models import RefreshToken, Role, User
from app.models.user import ROLE_LEVEL
from app.schemas.common import Page, UserCreate, UserOut, UserUpdate
from app.services.audit import audit

router = APIRouter(prefix="/users", tags=["team"])


def _check_can_manage(actor: User, target_role: str) -> None:
    if target_role not in ROLE_LEVEL:
        raise HTTPException(400, "Unknown role")
    if ROLE_LEVEL[target_role] >= ROLE_LEVEL["admin"] and not actor.has_role("super_admin"):
        raise HTTPException(403, "Only a Super Admin can manage administrators")


@router.get("/roles")
def roles(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [{"name": r.name, "display_name": r.display_name, "description": r.description} for r in db.scalars(select(Role).order_by(Role.id))]


@router.get("", response_model=Page[UserOut])
def list_users(
    q: str | None = None, role: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    _: User = Depends(require_admin), db: Session = Depends(get_db),
):
    stmt = select(User).join(Role)
    if q:
        stmt = stmt.where(or_(User.email.ilike(f"%{q}%"), User.full_name.ilike(f"%{q}%")))
    if role:
        stmt = stmt.where(Role.name == role)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    users = db.scalars(stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=[user_out(u) for u in users], total=total, page=page, page_size=page_size)


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, request: Request, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    _check_can_manage(actor, body.role)
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "A user with this e-mail already exists")
    if err := validate_password_strength(body.password):
        raise HTTPException(400, err)
    role = db.scalar(select(Role).where(Role.name == body.role))
    u = User(email=body.email.lower(), full_name=body.full_name.strip(), password_hash=hash_password(body.password), role_id=role.id)
    db.add(u)
    db.flush()
    audit(db, actor, "user.create", "user", u.id, f"Created {u.email} as {role.name}", request=request)
    db.commit()
    db.refresh(u)
    return user_out(u)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, request: Request, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    _check_can_manage(actor, u.role.name)
    changes = {}
    if body.role is not None and body.role != u.role.name:
        _check_can_manage(actor, body.role)
        if u.id == actor.id:
            raise HTTPException(400, "You cannot change your own role")
        if u.role.name == "super_admin" and _super_admin_count(db) <= 1:
            raise HTTPException(400, "At least one Super Admin is required")
        u.role_id = db.scalar(select(Role.id).where(Role.name == body.role))
        changes["role"] = body.role
    if body.full_name is not None:
        u.full_name = body.full_name.strip()
        changes["full_name"] = u.full_name
    if body.is_active is not None and body.is_active != u.is_active:
        if u.id == actor.id:
            raise HTTPException(400, "You cannot deactivate your own account")
        u.is_active = body.is_active
        changes["is_active"] = body.is_active
        if not body.is_active:
            db.execute(update(RefreshToken).where(RefreshToken.user_id == u.id, RefreshToken.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))
    audit(db, actor, "user.update", "user", u.id, f"Updated {u.email}", changes, request=request)
    db.commit()
    db.refresh(u)
    return user_out(u)


def _super_admin_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User).join(Role).where(Role.name == "super_admin", User.is_active.is_(True)))


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, request: Request, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    _check_can_manage(actor, u.role.name)
    if u.id == actor.id:
        raise HTTPException(400, "You cannot delete your own account")
    if u.role.name == "super_admin" and _super_admin_count(db) <= 1:
        raise HTTPException(400, "At least one Super Admin is required")
    audit(db, actor, "user.delete", "user", u.id, f"Deleted {u.email}", request=request)
    db.delete(u)
    db.commit()


@router.post("/{user_id}/reset-link")
def admin_reset_link(user_id: int, request: Request, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Generates a one-time password reset link to hand to the user (useful without SMTP)."""
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    _check_can_manage(actor, u.role.name)
    token = create_reset_token(db, u)
    audit(db, actor, "user.reset_link", "user", u.id, f"Generated reset link for {u.email}", request=request)
    db.commit()
    s = get_settings()
    return {"reset_url": f"{s.frontend_origin}/reset-password?token={token}", "expires_minutes": s.password_reset_minutes}
