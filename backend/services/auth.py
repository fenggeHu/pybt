import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..models import AuthToken, User

SECRET = os.environ.get("PYBT_AUTH_SECRET", "pybt-secret")
ALGO = "HS256"
TOKEN_MINUTES = 60 * 24

bearer_scheme = HTTPBearer(auto_error=False)


def create_token(user: User, expires_minutes: int = TOKEN_MINUTES) -> AuthToken:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.username,
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }
    token = jwt.encode(payload, SECRET, algorithm=ALGO)
    return AuthToken(access_token=token, user=user)


def decode_token(token: str) -> User:
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGO])
        return User(username=payload["sub"], role=payload.get("role", "user"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="auth required")
    return decode_token(credentials.credentials)
