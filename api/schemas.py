from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DatasetInfo(BaseModel):
    id: str
    name: str
    path: str
    symbols: List[str] = Field(default_factory=list)
    rows: int = 0
    start: Optional[datetime] = None
    end: Optional[datetime] = None


class StrategyConfig(BaseModel):
    id: str
    name: str
    type: str
    params: Dict[str, object] = Field(default_factory=dict)
    updatedAt: datetime


class StrategyPayload(BaseModel):
    id: Optional[str] = None
    name: str
    type: str
    params: Dict[str, object] = Field(default_factory=dict)


class RiskConfigPayload(BaseModel):
    maxUnits: int = 100
    stopLossPct: float = 0.0


class AllocatorConfigPayload(BaseModel):
    maxLeverage: float = 1.0
    lotSize: int = 1
    rounding: str = "round"


class BacktestRequest(BaseModel):
    datasetId: str
    strategyIds: List[str]
    cash: float = 100_000.0
    slipBps: float = 1.0
    commission: float = 0.0
    commissionRate: float = 0.0
    volumeLimit: float = 1.0
    risk: RiskConfigPayload = RiskConfigPayload()
    allocator: Optional[AllocatorConfigPayload] = None
    notes: Optional[str] = None


class BacktestSummary(BaseModel):
    id: str
    name: str
    status: str
    startedAt: datetime
    finishedAt: Optional[datetime] = None
    totalReturn: Optional[float] = None
    sharpe: Optional[float] = None
    maxDrawdown: Optional[float] = None


class EquityPoint(BaseModel):
    dt: str
    equity: float


class TradeRecord(BaseModel):
    symbol: str
    side: str
    qty: int
    entry_dt: str
    exit_dt: str
    pnl: float
    ret: Optional[float] = None
    tag: Optional[str] = None


class BacktestResult(BaseModel):
    summary: BacktestSummary
    metrics: Dict[str, float]
    equity: List[EquityPoint]
    trades: List[TradeRecord]
    logs: List[str] = Field(default_factory=list)


class BacktestResponse(BaseModel):
    task_id: str
