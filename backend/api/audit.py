from fastapi import APIRouter, Depends

from ..models import AuditLog, User
from ..services import store
from ..services.auth import require_permission

router = APIRouter(tags=["audit"])


@router.get("/audit", response_model=list[AuditLog])
async def list_audit(user: User = Depends(require_permission("audit.read"))) -> list[AuditLog]:
    return store.audit_logs[-200:]
