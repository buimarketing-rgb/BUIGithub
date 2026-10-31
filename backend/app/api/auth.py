"""Authentication: login, refresh-token rotation (httpOnly cookie), logout, password reset.

Access tokens are short-lived JWTs sent as Bearer headers (not CSRF-able). The refresh token is
an opaque random string in an httpOnly, SameSite=Strict cookie scoped to /api/auth, and the
refresh/logout endpoints additionally require a custom header (X-Requested-With) as CSRF defence.
Reuse of a rotated refresh token revokes the whole token family (theft detection)."""
import logging
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import client_ip, get_current_user, rate_limit
from app.core.security import (
    create_access_token, hash_password, hash_token, needs_rehash, new_opaque_token, validate_password_strength, verify_password,
)
from app.models import PasswordResetToken, RefreshToken, User
from app.schemas.common import ForgotPasswordIn, LoginIn, PasswordChange, ProfileUpdate, ResetPasswordIn, TokenOut, UserOut
from app.services.audit import audit

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger(__name__)
COOKIE = "bui_refresh"


def user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id, email=u.email, full_name=u.full_name, role=u.role.name, is_active=u.is_active,
        preferred_language=u.preferred_language, last_login_at=u.last_login_at, created_at=u.created_at,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require_csrf_header(request: Request) -> None:
    if request.headers.get("x-requested-with") != "BUI":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing CSRF header")


def _issue(db: Session, user: User, response: Response, request: Request, family: str | None = None) -> TokenOut:
    s = get_settings()
    token, token_hash = new_opaque_token()
    rt = RefreshToken(
        user_id=user.id, token_hash=token_hash, family_id=family or str(uuid.uuid4()),
        expires_at=_now() + timedelta(days=s.refresh_token_days), user_agent=(request.headers.get("user-agent") or "")[:300],
    )
    db.add(rt)
    db.flush()
    response.set_cookie(
        COOKIE, token, max_age=s.refresh_token_days * 86400, httponly=True, secure=s.cookie_secure,
        samesite="strict", path=f"{s.api_prefix}/auth",
    )
    return TokenOut(access_token=create_access_token(user.id, user.role.name), expires_in=s.access_token_minutes * 60, user=user_out(user)), rt


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    s = get_settings()
    rate_limit("login", s.login_rate_limit_per_minute, 60, client_ip(request))
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        audit(db, user, "auth.login_failed", "user", user.id if user else None, f"Failed login for {body.email}", request=request)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your account has been disabled. Contact an administrator.")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    user.last_login_at = _now()
    out, _ = _issue(db, user, response, request)
    audit(db, user, "auth.login", "user", user.id, "Signed in", request=request)
    db.commit()
    return out


@router.post("/refresh", response_model=TokenOut)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    _require_csrf_header(request)
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No session")
    rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(token)))
    if rt is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")
    if rt.revoked_at is not None:
        # Token reuse -> possible theft: revoke the entire family
        db.execute(update(RefreshToken).where(RefreshToken.family_id == rt.family_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=_now()))
        audit(db, None, "auth.refresh_reuse_detected", "user", rt.user_id, "Refresh token reuse detected; sessions revoked", request=request)
        db.commit()
        response.delete_cookie(COOKIE, path=f"{get_settings().api_prefix}/auth")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    if rt.expires_at < _now():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    user = db.get(User, rt.user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account disabled")
    out, new_rt = _issue(db, user, response, request, family=rt.family_id)
    rt.revoked_at = _now()
    rt.replaced_by_id = new_rt.id
    db.commit()
    return out


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    _require_csrf_header(request)
    token = request.cookies.get(COOKIE)
    if token:
        rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(token)))
        if rt:
            db.execute(update(RefreshToken).where(RefreshToken.family_id == rt.family_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=_now()))
            db.commit()
    response.delete_cookie(COOKIE, path=f"{get_settings().api_prefix}/auth")
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.patch("/me", response_model=UserOut)
def update_me(body: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.full_name is not None:
        user.full_name = body.full_name.strip()
    if body.preferred_language is not None:
        user.preferred_language = body.preferred_language
    db.commit()
    return user_out(user)


@router.post("/change-password", status_code=204)
def change_password(body: PasswordChange, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    if err := validate_password_strength(body.new_password):
        raise HTTPException(400, err)
    user.password_hash = hash_password(body.new_password)
    audit(db, user, "auth.password_changed", "user", user.id, "Password changed", request=request)
    db.commit()


def create_reset_token(db: Session, user: User) -> str:
    token, token_hash = new_opaque_token()
    db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=_now() + timedelta(minutes=get_settings().password_reset_minutes)))
    return token


def _send_reset_email(user: User, link: str) -> bool:
    s = get_settings()
    if not s.smtp_host:
        return False
    msg = EmailMessage()
    msg["Subject"] = "Reset your BUI password"
    msg["From"] = s.smtp_from
    msg["To"] = user.email
    msg.set_content(f"Hello {user.full_name},\n\nReset your BUI password using this link (valid for {s.password_reset_minutes} minutes):\n{link}\n\nIf you did not request this, ignore this e-mail.")
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password or "")
            smtp.send_message(msg)
        return True
    except Exception:
        log.exception("Failed to send reset e-mail")
        return False


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordIn, request: Request, db: Session = Depends(get_db)):
    rate_limit("forgot", 5, 300, client_ip(request))
    user = db.scalar(select(User).where(User.email == body.email.lower(), User.is_active.is_(True)))
    if user:
        token = create_reset_token(db, user)
        link = f"{get_settings().frontend_origin}/reset-password?token={token}"
        if not _send_reset_email(user, link):
            log.warning("SMTP not configured: password reset requested for %s. An administrator can issue a reset link from Team Management.", user.email)
        audit(db, user, "auth.password_reset_requested", "user", user.id, "Password reset requested", request=request)
        db.commit()
    # Same response either way (no account enumeration)
    return {"message": "If an account exists for that e-mail, reset instructions have been sent. If you don't receive an e-mail, ask your administrator for a reset link."}


@router.post("/reset-password", status_code=204)
def reset_password(body: ResetPasswordIn, request: Request, db: Session = Depends(get_db)):
    rate_limit("reset", 10, 300, client_ip(request))
    prt = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(body.token)))
    if not prt or prt.used_at is not None or prt.expires_at < _now():
        raise HTTPException(400, "This reset link is invalid or has expired.")
    if err := validate_password_strength(body.new_password):
        raise HTTPException(400, err)
    user = db.get(User, prt.user_id)
    user.password_hash = hash_password(body.new_password)
    prt.used_at = _now()
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)).values(revoked_at=_now()))
    audit(db, user, "auth.password_reset", "user", user.id, "Password reset via link", request=request)
    db.commit()
