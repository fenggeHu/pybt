from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Optional

from .enums import OrderSide, OrderType, SignalDirection


@dataclass(frozen=True)
class Event:
    """
    Base class for all events moving through the backtest.

    Events carry a timestamp to preserve ordering when multiple events
    are emitted at the same simulated time slice.
    """

    timestamp: datetime

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(ts={self.timestamp.isoformat()})"


@dataclass(frozen=True)
class MarketEvent(Event):
    """
    Represents new market data for a particular symbol.
    """

    symbol: str
    fields: Mapping[str, float]


@dataclass(frozen=True)
class SignalEvent(Event):
    """
    Strategy signal indicating desired exposure change.
    """

    strategy_id: str
    symbol: str
    direction: SignalDirection
    strength: float = 1.0
    meta: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderEvent(Event):
    """
    Portfolio instruction for the execution handler.
    """

    symbol: str
    quantity: int
    order_type: OrderType
    direction: OrderSide
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    meta: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class FillEvent(Event):
    """
    Execution report returned by the execution handler.
    """

    order_id: str
    symbol: str
    quantity: int
    fill_price: float
    commission: float = 0.0
    meta: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class MetricsEvent(Event):
    """
    Periodic event carrying computed performance metrics.
    """

    payload: Mapping[str, float]
