from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.cache import get_cache
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import ROLE_ADMIN, ROLE_SUPER_ADMIN, ROLE_TEAM_MEMBER, User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = decode_access_token(creds.credentials)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account disabled or not found")
    return user


def require_role(minimum: str) -> Callable[[User], User]:
    def checker(user: User = Depends(get_current_user)) -> User:
        if not user.has_role(minimum):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to perform this action")
        return user

    return checker


require_member = require_role(ROLE_TEAM_MEMBER)
require_admin = require_role(ROLE_ADMIN)
require_super_admin = require_role(ROLE_SUPER_ADMIN)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str, limit: int, window_seconds: int, identity: str) -> None:
    """Fixed-window rate limiter backed by Redis (or memory)."""
    count = get_cache().incr(f"rl:{bucket}:{identity}", window_seconds)
    if count > limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many requests. Please wait a moment and try again.",
            headers={"Retry-After": str(window_seconds)},
        )
