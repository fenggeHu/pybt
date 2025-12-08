from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ..models import AuthToken, User
from ..services.auth import create_token, get_current_user
from ..services import store

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login", response_model=AuthToken)
async def login(payload: LoginRequest) -> AuthToken:
    user = store.authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username or password")
    token = create_token(user)
    store.add_audit(actor=user.username, action="login", target="self", detail="login success")
    return token


@router.post("/auth/register", response_model=AuthToken, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest) -> AuthToken:
    try:
        user = store.register_user(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    token = create_token(user)
    store.add_audit(actor=user.username, action="register", target="self", detail="register success")
    return token


@router.get("/auth/me", response_model=User)
async def me(user: User = get_current_user) -> User:
    return user
