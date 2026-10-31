"""Password hashing (Argon2id), JWT access tokens and opaque refresh/reset tokens."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings

_hasher = PasswordHasher()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def validate_password_strength(password: str) -> str | None:
    """Returns an error message, or None when the password is acceptable."""
    if len(password) < 10:
        return "Password must be at least 10 characters long."
    if password.lower() == password or password.upper() == password:
        return "Password must contain both upper- and lower-case letters."
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one number."
    return None


def create_access_token(user_id: int, role: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    return payload


def new_opaque_token() -> tuple[str, str]:
    """Returns (token, sha256 hash). Only the hash is persisted."""
    token = secrets.token_urlsafe(48)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def sign_file_url(kind: str, object_id: int, ttl_seconds: int = 3600) -> str:
    """Short-lived signed URL so <img>/<a> tags can load protected files without a Bearer header."""
    import hmac
    import time

    exp = int(time.time()) + ttl_seconds
    sig = hmac.new(get_settings().secret_key.encode(), f"{kind}:{object_id}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{get_settings().api_prefix}/files/{kind}/{object_id}?exp={exp}&sig={sig}"


def verify_file_signature(kind: str, object_id: int, exp: int, sig: str) -> bool:
    import hmac
    import time

    if exp < time.time():
        return False
    expected = hmac.new(get_settings().secret_key.encode(), f"{kind}:{object_id}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(expected, sig)
