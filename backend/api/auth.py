from fastapi import APIRouter
from pydantic import BaseModel

from ..models import AuthToken, User
from ..services.auth import create_token, get_current_user
from ..services import store

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login", response_model=AuthToken)
async def login(payload: LoginRequest) -> AuthToken:
    user = User(username=payload.username, role="admin")
    token = create_token(user)
    store.add_audit(actor=user.username, action="login", target="self", detail="login success")
    return token


@router.get("/auth/me", response_model=User)
async def me(user: User = get_current_user) -> User:
    return user
