import logging
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4
from typing import Iterable, List, Optional, Sequence

from .event_bus import EventBus
from .events import FillEvent, MarketEvent, MetricsEvent, OrderEvent, SignalEvent
from .interfaces import (
    BusParticipant,
    DataFeed,
    ExecutionHandler,
    PerformanceReporter,
    Portfolio,
    RiskManager,
    Strategy,
)
from pybt.logging import log_event


@dataclass
class EngineConfig:
    """
    Lightweight configuration bundle for the engine.
    """

    name: str = "backtest"
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    run_id: str = field(default_factory=lambda: uuid4().hex[:8])


class BacktestEngine:
    """
    Coordinates the event-driven backtest wiring the modular components.
    """

    def __init__(
            self,
            data_feed: DataFeed,
            strategies: Sequence[Strategy],
            portfolio: Portfolio,
            execution: ExecutionHandler,
            risk_managers: Optional[Sequence[RiskManager]] = None,
            reporters: Optional[Sequence[PerformanceReporter]] = None,
            bus: Optional[EventBus] = None,
            config: Optional[EngineConfig] = None,
    ) -> None:
        self.data_feed = data_feed
        self.strategies: List[Strategy] = list(strategies)
        self.portfolio = portfolio
        self.execution = execution
        self.risk_managers: List[RiskManager] = list(risk_managers or [])
        self.reporters: List[PerformanceReporter] = list(reporters or [])
        self.bus = bus or EventBus()
        self.config = config or EngineConfig()
        self._running: bool = False
        self._logger = logging.getLogger(__name__)

        self._bind_components()
        self._register_routes()

    def _bind_components(self) -> None:
        for component in self._components:
            component.bind(self.bus)

    @property
    def _components(self) -> Iterable[BusParticipant]:
        yield self.data_feed
        yield from self.strategies
        yield self.portfolio
        yield self.execution
        yield from self.risk_managers
        yield from self.reporters

    def _register_routes(self) -> None:
        self.bus.subscribe(MarketEvent, self._route_market)
        self.bus.subscribe(SignalEvent, self._route_signal)
        self.bus.subscribe(OrderEvent, self._route_order)
        self.bus.subscribe(FillEvent, self._route_fill)
        self.bus.subscribe(MetricsEvent, self._route_metrics)

    def run(self) -> None:
        if self._running:
            raise RuntimeError("BacktestEngine is already running.")

        self._running = True
        cycle = 0
        try:
            self._logger.info("Starting backtest '%s' run_id=%s", self.config.name, self.config.run_id)
            for component in self._components:
                component.on_start()

            self.data_feed.prime()

            while self.data_feed.has_next():
                self.data_feed.next()
                self.bus.dispatch()
                self._emit_metrics()
                cycle += 1
        finally:
            for component in self._components:
                component.on_stop()
            self._running = False
            self._logger.info(
                "Backtest '%s' completed (cycles=%d, run_id=%s)", self.config.name, cycle, self.config.run_id
            )

    def _route_market(self, event: MarketEvent) -> None:
        self._logger.debug("MarketEvent %s", event)
        log_event(self._logger, event, level="DEBUG")
        for strategy in self.strategies:
            strategy.on_market(event)

    def _route_signal(self, event: SignalEvent) -> None:
        self._logger.debug("SignalEvent %s", event)
        log_event(self._logger, event, level="DEBUG")
        self.portfolio.on_signal(event)

    def _route_order(self, event: OrderEvent) -> None:
        self._logger.debug("OrderEvent %s", event)
        log_event(self._logger, event, level="DEBUG")
        order: Optional[OrderEvent] = event
        for risk in self.risk_managers:
            if order is None:
                break
            order = risk.review(order)
        if order is None:
            return
        self.execution.on_order(order)

    def _route_fill(self, event: FillEvent) -> None:
        self._logger.debug("FillEvent %s", event)
        log_event(self._logger, event, level="DEBUG")
        self.portfolio.on_fill(event)
        for reporter in self.reporters:
            reporter.on_fill(event)

    def _route_metrics(self, event: MetricsEvent) -> None:
        """
        Default handler simply publishes metrics downstream. Users can
        override or extend behaviour by subscribing directly.
        """

        # Nothing to do—events remain on the bus for external subscribers.
        # Method kept for symmetry and potential logging hooks.
        return

    def _emit_metrics(self) -> None:
        metrics_events: List[MetricsEvent] = []
        for reporter in self.reporters:
            metrics_events.extend(reporter.emit_metrics())
        if not metrics_events:
            return
        self.bus.drain(metrics_events)
        self.bus.dispatch()
