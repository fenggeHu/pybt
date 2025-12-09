from fastapi import APIRouter, Depends

from ..models import DefinitionItem, User
from ..services import list_definitions
from ..services.auth import require_permission

router = APIRouter(tags=["definitions"])


@router.get("/definitions", response_model=list[DefinitionItem])
async def definitions(user: User = Depends(require_permission("configs.read"))) -> list[DefinitionItem]:
    return list_definitions()
