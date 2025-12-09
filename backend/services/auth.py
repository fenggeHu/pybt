import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..models import AuthToken, User
from .rbac import rbac_service

SECRET = os.environ.get("PYBT_AUTH_SECRET", "pybt-secret")
ALGO = "HS256"
TOKEN_MINUTES = 60 * 24

bearer_scheme = HTTPBearer(auto_error=False)


def create_token(user: User, expires_minutes: int = TOKEN_MINUTES) -> AuthToken:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.username,
        "role": user.role,
        "roles": user.roles,
        "perms": user.permissions,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }
    token = jwt.encode(payload, SECRET, algorithm=ALGO)
    return AuthToken(access_token=token, user=user)


def decode_token(token: str) -> User:
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGO])
        user = rbac_service.get_user(payload["sub"])
        if not user or not user.active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found or inactive")
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="auth required")
    return decode_token(credentials.credentials)


def require_permission(permission: str):
    """Dependency factory to enforce a permission on a route."""

    def _permission_guard(user: User = Depends(get_current_user)) -> User:
        if permission not in user.permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
        return user

    return _permission_guard
