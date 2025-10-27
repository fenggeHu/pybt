"""
Modular event-driven backtesting framework.

The :mod:`pybt.core` package aggregates fundamental primitives
(:class:`BacktestEngine`, events, enums, interfaces), while dedicated
subpackages (:mod:`pybt.data`, :mod:`pybt.strategies`, :mod:`pybt.execution`,
:mod:`pybt.portfolio`, :mod:`pybt.risk`, :mod:`pybt.analytics`) provide
extensible component implementations. Everything re-exports here for a
streamlined developer experience.
"""

from . import analytics, core, data, execution, portfolio, risk, strategies
from .core import (
    BacktestEngine,
    Bar,
    EngineConfig,
    Event,
    EventBus,
    Exposure,
    FillEvent,
    MarketEvent,
    MetricsEvent,
    OrderEvent,
    OrderSide,
    OrderType,
    SignalDirection,
    SignalEvent,
)

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
    "analytics",
    "core",
    "data",
    "execution",
    "portfolio",
    "risk",
    "strategies",
]
