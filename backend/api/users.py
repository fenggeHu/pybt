from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..models import Permission, Role, User
from ..services import store
from ..services.auth import require_permission
from ..services.rbac import rbac_service

router = APIRouter(tags=["users"])


class UserCreate(BaseModel):
    username: str
    password: str
    roles: list[str] = Field(default_factory=list)


class UserRolesUpdate(BaseModel):
    roles: list[str]


class RoleCreate(BaseModel):
    name: str
    permissions: list[str]
    description: str | None = None


class RoleUpdate(BaseModel):
    permissions: list[str]
    description: str | None = None


@router.get("/users", response_model=list[User])
async def list_users(_: User = Depends(require_permission("users.manage"))) -> list[User]:
    return rbac_service.list_users()


@router.post("/users", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, actor: User = Depends(require_permission("users.manage"))) -> User:
    try:
        user = rbac_service.create_user(payload.username, payload.password, roles=payload.roles)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    store.add_audit(actor=actor.username, action="create_user", target=user.username)
    return user


@router.put("/users/{username}/roles", response_model=User)
async def update_user_roles(
    username: str, payload: UserRolesUpdate, actor: User = Depends(require_permission("users.manage"))
) -> User:
    try:
        user = rbac_service.set_user_roles(username, payload.roles)
    except ValueError as exc:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc))
    store.add_audit(
        actor=actor.username,
        action="update_user_roles",
        target=username,
        detail=",".join(payload.roles),
    )
    return user


@router.get("/roles", response_model=list[Role])
async def list_roles(_: User = Depends(require_permission("users.manage"))) -> list[Role]:
    return rbac_service.list_roles()


@router.post("/roles", response_model=Role, status_code=status.HTTP_201_CREATED)
async def create_role(payload: RoleCreate, actor: User = Depends(require_permission("users.manage"))) -> Role:
    try:
        role = rbac_service.create_role(payload.name, payload.permissions, payload.description)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    store.add_audit(actor=actor.username, action="create_role", target=payload.name)
    return role


@router.put("/roles/{role_name}", response_model=Role)
async def update_role(
    role_name: str, payload: RoleUpdate, actor: User = Depends(require_permission("users.manage"))
) -> Role:
    try:
        role = rbac_service.update_role_permissions(role_name, payload.permissions, payload.description)
    except ValueError as exc:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc))
    store.add_audit(actor=actor.username, action="update_role", target=role_name)
    return role


@router.get("/permissions", response_model=list[Permission])
async def list_permissions(_: User = Depends(require_permission("users.manage"))) -> list[Permission]:
    return rbac_service.list_permissions()
