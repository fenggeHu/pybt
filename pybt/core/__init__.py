"""
Core primitives for the event-driven backtesting framework.

Exports the engine, event bus, event models, enums, and component
interfaces used throughout the system.
"""

from .engine import BacktestEngine, EngineConfig
from .enums import Exposure, OrderSide, OrderType, SignalDirection
from .event_bus import EventBus
from .events import Event, FillEvent, MarketEvent, MetricsEvent, OrderEvent, SignalEvent
from .interfaces import (
    BusParticipant,
    DataFeed,
    ExecutionHandler,
    PerformanceReporter,
    Portfolio,
    RiskManager,
    Strategy,
)
from .models import Bar

__all__ = [
    "BacktestEngine",
    "EngineConfig",
    "EventBus",
    "Event",
    "MarketEvent",
    "SignalEvent",
    "OrderEvent",
    "FillEvent",
    "MetricsEvent",
    "Exposure",
    "SignalDirection",
    "OrderSide",
    "OrderType",
    "Bar",
    "BusParticipant",
    "DataFeed",
    "Strategy",
    "Portfolio",
    "ExecutionHandler",
    "RiskManager",
    "PerformanceReporter",
]
