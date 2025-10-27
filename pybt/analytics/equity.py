from collections import defaultdict
from datetime import datetime
from typing import DefaultDict, Dict, Iterable

from pybt.core.events import FillEvent, MarketEvent, MetricsEvent
from pybt.core.interfaces import PerformanceReporter


class EquityCurveReporter(PerformanceReporter):
    """
    Tracks equity curve and emits metrics after each engine cycle.
    """

    def __init__(self, initial_cash: float = 100_000.0) -> None:
        super().__init__()
        self.initial_cash = initial_cash
        self._cash: float = initial_cash
        self._positions: DefaultDict[str, int] = defaultdict(int)
        self._prices: Dict[str, float] = {}
        self._last_timestamp: datetime | None = None

    def on_start(self) -> None:
        self._cash = self.initial_cash
        self._positions.clear()
        self._prices.clear()
        self._last_timestamp = None
        self.bus.subscribe(MarketEvent, self._on_market)

    def on_stop(self) -> None:
        self.bus.unsubscribe(MarketEvent, self._on_market)

    def on_fill(self, event: FillEvent) -> None:
        self._positions[event.symbol] += event.quantity
        self._cash -= event.fill_price * event.quantity
        self._cash -= event.commission
        self._last_timestamp = event.timestamp

    def _on_market(self, event: MarketEvent) -> None:
        self._prices[event.symbol] = event.fields["close"]
        self._last_timestamp = event.timestamp

    def _equity(self) -> float:
        inventory = sum(self._positions[symbol] * self._prices.get(symbol, 0.0) for symbol in self._positions)
        return self._cash + inventory

    def emit_metrics(self) -> Iterable[MetricsEvent]:
        if self._last_timestamp is None:
            return []
        equity = self._equity()
        gross = sum(abs(self._positions[symbol]) * self._prices.get(symbol, 0.0) for symbol in self._positions)
        metrics = MetricsEvent(
            timestamp=self._last_timestamp,
            payload={"equity": equity, "cash": self._cash, "gross_exposure": gross},
        )
        return [metrics]
