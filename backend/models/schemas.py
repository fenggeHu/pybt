from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class DataSource(BaseModel):
    id: str
    name: str
    type: str = Field(..., description="local_csv | rest | websocket | adata | custom")
    path: Optional[str] = None
    symbol: Optional[str] = None
    description: Optional[str] = None
    healthy: Optional[bool] = None
    last_checked: Optional[datetime] = None


class ConfigTemplate(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class Run(BaseModel):
    id: str
    name: str
    config_id: Optional[str] = None
    config: dict[str, Any]
    status: RunStatus
    created_at: datetime
    updated_at: datetime
    progress: Optional[float] = None
    message: Optional[str] = None
    artifacts: list[str] = []


class RunCreate(BaseModel):
    name: str
    config_id: Optional[str] = None
    config: Optional[dict[str, Any]] = None


class DefinitionParam(BaseModel):
    name: str
    type: str
    required: bool = True
    default: Optional[Any] = None
    description: Optional[str] = None


class DefinitionItem(BaseModel):
    category: str
    type: str
    summary: str
    params: list[DefinitionParam] = []


class User(BaseModel):
    username: str
    role: str = "admin"


class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User


class ValidationResult(BaseModel):
    ok: bool
    detail: Optional[str] = None


class AuditLog(BaseModel):
    id: str
    actor: str
    action: str
    target: str
    timestamp: datetime
    detail: Optional[str] = None
