from pybt.core.events import MarketEvent, OrderEvent
from pybt.core.interfaces import RiskManager


class PriceBandRisk(RiskManager):
    """Rejects orders deviating too far from the last observed price.

    band_pct defines the maximum allowed deviation (e.g., 0.05 = 5%).
    """

    def __init__(self, band_pct: float = 0.05) -> None:
        super().__init__()
        if band_pct <= 0:
            raise ValueError("band_pct must be positive")
        self.band_pct = band_pct
        self._last_prices: dict[str, float] = {}

    def on_start(self) -> None:
        self._last_prices.clear()
        self.bus.subscribe(MarketEvent, self._on_market)

    def on_stop(self) -> None:
        self.bus.unsubscribe(MarketEvent, self._on_market)

    def _on_market(self, event: MarketEvent) -> None:
        self._last_prices[event.symbol] = event.fields["close"]

    def review(self, order: OrderEvent) -> OrderEvent | None:
        last = self._last_prices.get(order.symbol)
        if last is None:
            return None
        limit = order.limit_price or last
        deviation = abs(limit - last) / last if last else 0.0
        if deviation > self.band_pct:
            return None
        return order


__all__ = ["PriceBandRisk"]
