from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..services.database import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: Session = Depends(get_session)) -> dict[str, Any]:
    health_status: dict[str, Any] = {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "ok",
    }
    
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        health_status["status"] = "error"
        health_status["database"] = "error"
        health_status["detail"] = str(e)
        # In a real app we might return 503, but here we just return the status details
    
    return health_status
