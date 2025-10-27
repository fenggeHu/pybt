from abc import ABC, abstractmethod
from typing import Iterable, Optional

from .event_bus import EventBus
from .events import FillEvent, MarketEvent, MetricsEvent, OrderEvent, SignalEvent

__all__ = [
    "BusParticipant",
    "DataFeed",
    "Strategy",
    "Portfolio",
    "ExecutionHandler",
    "RiskManager",
    "PerformanceReporter",
]


class BusParticipant(ABC):
    """
    Base class for components that need access to the event bus.
    """

    def __init__(self) -> None:
        self._bus: Optional[EventBus] = None

    def bind(self, bus: EventBus) -> None:
        self._bus = bus

    @property
    def bus(self) -> EventBus:
        if self._bus is None:
            raise RuntimeError("Component not bound to an EventBus.")
        return self._bus

    def on_start(self) -> None:
        """
        Lifecycle hook invoked before the backtest starts dispatching events.
        """

    def on_stop(self) -> None:
        """
        Lifecycle hook invoked once the backtest completes.
        """


class DataFeed(BusParticipant):
    """
    Source of market data feeding the engine with market events.
    """

    @abstractmethod
    def prime(self) -> None:
        """
        Prepare internal state (seek to start date, load caches, etc.).
        """

    @abstractmethod
    def has_next(self) -> bool:
        """
        Return True while additional data slices remain.
        """

    @abstractmethod
    def next(self) -> None:
        """
        Produce the next set of events by publishing to the bus.
        """


class Strategy(BusParticipant):
    """
    Turns market data into trading signals.
    """

    @abstractmethod
    def on_market(self, event: MarketEvent) -> None:
        """
        Strategy reaction to new market data.
        """


class Portfolio(BusParticipant):
    """
    Converts signals into orders and tracks positions.
    """

    @abstractmethod
    def on_signal(self, event: SignalEvent) -> None:
        """
        Transform the signal into order intents and publish them.
        """

    def on_fill(self, event: FillEvent) -> None:
        """
        Update internal state given new fill execution.
        """


class ExecutionHandler(BusParticipant):
    """
    Simulates order execution and returns fills.
    """

    @abstractmethod
    def on_order(self, event: OrderEvent) -> None:
        """
        Fill or reject the incoming order and publish result events.
        """


class RiskManager(BusParticipant):
    """
    Filters orders, enforcing risk constraints before execution.
    """

    def review(self, order: OrderEvent) -> Optional[OrderEvent]:
        """
        Return the order (possibly modified) if the execution is allowed,
        or None to drop the order entirely.
        """

        return order


class PerformanceReporter(BusParticipant):
    """
    Records fills and periodically emits performance metrics.
    """

    def on_fill(self, event: FillEvent) -> None:
        """
        Accumulate portfolio performance given a new fill.
        """

    def emit_metrics(self) -> Iterable[MetricsEvent]:
        """
        Create metrics events to report current state.
        """

        return []
