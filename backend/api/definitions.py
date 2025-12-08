from fastapi import APIRouter, Depends

from ..models import DefinitionItem, User
from ..services import list_definitions
from ..services.auth import get_current_user

router = APIRouter(tags=["definitions"])


@router.get("/definitions", response_model=list[DefinitionItem])
async def definitions(user: User = Depends(get_current_user)) -> list[DefinitionItem]:
    return list_definitions()
