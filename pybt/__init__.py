"""
Modular event-driven backtesting framework.

The :mod:`pybt.core` package aggregates fundamental primitives
(:class:`BacktestEngine`, events, enums, interfaces), while dedicated
subpackages (:mod:`pybt.data`, :mod:`pybt.strategies`, :mod:`pybt.execution`,
:mod:`pybt.portfolio`, :mod:`pybt.risk`, :mod:`pybt.analytics`) provide
extensible component implementations. Everything re-exports here for a
streamlined developer experience.
"""

from pybt import analytics, core, data, execution, portfolio, risk, strategies
from pybt.analytics import DetailedReporter, EquityCurveReporter
from pybt.errors import (
    ConfigurationError,
    DataError,
    ExecutionError,
    FeedError,
    PersistenceError,
    PyBTError,
    RiskError,
)
from pybt.configuration import load_engine_from_dict, load_engine_from_json
from pybt.core import (
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
from pybt.core.logging import configure_logging, log_event

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
    "EquityCurveReporter",
    "DetailedReporter",
    "PyBTError",
    "ConfigurationError",
    "DataError",
    "ExecutionError",
    "FeedError",
    "PersistenceError",
    "RiskError",
    "log_event",
    "load_engine_from_dict",
    "load_engine_from_json",
    "configure_logging",
    "analytics",
    "core",
    "data",
    "execution",
    "portfolio",
    "risk",
    "strategies",
]
