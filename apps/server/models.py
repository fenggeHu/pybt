from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Mapping, Optional

from pydantic import BaseModel, Field


class ErrorDTO(BaseModel):
    message: str
    details: Optional[Mapping[str, Any]] = None


class ConfigSaveResponse(BaseModel):
    ok: bool = True
    name: str


class ConfigValidateRequest(BaseModel):
    config: Mapping[str, Any]


class ConfigValidateResponse(BaseModel):
    ok: bool
    error: Optional[ErrorDTO] = None


class RunCreateRequest(BaseModel):
    config_name: Optional[str] = None
    config: Optional[Mapping[str, Any]] = None


class RunCreateResponse(BaseModel):
    ok: bool = True
    run_id: str
    config_name: str


RunState = Literal["starting", "running", "stopped", "completed", "failed"]


class RunStatusDTO(BaseModel):
    run_id: str
    state: RunState
    pid: Optional[int] = None
    config_name: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    error: Optional[str] = None
    last_seq: int = 0


class EventDTO(BaseModel):
    seq: int
    received_at: datetime
    event_type: str
    timestamp: str
    data: Mapping[str, Any] = Field(default_factory=dict)


class EventsResponse(BaseModel):
    ok: bool = True
    run_id: str
    last_seq: int
    events: list[EventDTO]


class SummaryResponse(BaseModel):
    ok: bool
    run_id: str
    summary: Optional[Mapping[str, Any]] = None
    error: Optional[ErrorDTO] = None
