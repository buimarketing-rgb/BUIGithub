import logging
import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import Role, User

log = logging.getLogger(__name__)

ROLES = [
    ("super_admin", "Super Admin", "Full access: administrators, all company information and system configuration."),
    ("admin", "Admin", "Manage products, documents, FAQs, online research and team members."),
    ("team_member", "Team Member", "Ask questions, use the voice assistant, search products and view approved information."),
]


def ensure_roles(db: Session) -> None:
    existing = set(db.scalars(select(Role.name)))
    for name, display, desc in ROLES:
        if name not in existing:
            db.add(Role(name=name, display_name=display, description=desc))
    db.commit()


def ensure_initial_admin(db: Session) -> str | None:
    """Creates the first Super Admin when none exists. Returns a generated password, if any."""
    s = get_settings()
    has_super = db.scalar(select(func.count()).select_from(User).join(Role).where(Role.name == "super_admin", User.is_active.is_(True)))
    if has_super or db.scalar(select(User).where(User.email == s.initial_admin_email.lower())):
        return None
    password = s.initial_admin_password or secrets.token_urlsafe(12) + "A1a"
    role = db.scalar(select(Role).where(Role.name == "super_admin"))
    db.add(User(email=s.initial_admin_email.lower(), full_name=s.initial_admin_name, password_hash=hash_password(password), role_id=role.id))
    db.commit()
    if not s.initial_admin_password:
        log.warning(
            "\n\n================ BUI FIRST RUN ================\n"
            "Super Admin created:  %s\nTemporary password:   %s\n"
            "Sign in and change this password immediately (Settings > Profile).\n"
            "===============================================\n",
            s.initial_admin_email, password,
        )
        return password
    log.info("Super Admin %s created from INITIAL_ADMIN_PASSWORD", s.initial_admin_email)
    return None
