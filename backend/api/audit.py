from fastapi import APIRouter, Depends

from ..models import AuditLog, User
from ..services import store
from ..services.auth import get_current_user

router = APIRouter(tags=["audit"])


@router.get("/audit", response_model=list[AuditLog])
async def list_audit(user: User = Depends(get_current_user)) -> list[AuditLog]:
    return store.audit_logs[-200:]
