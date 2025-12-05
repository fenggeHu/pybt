import itertools
from datetime import datetime
from typing import Dict

from pybt.core.enums import OrderSide
from pybt.core.events import FillEvent, MarketEvent, OrderEvent
from pybt.core.interfaces import ExecutionHandler


class ImmediateExecutionHandler(ExecutionHandler):
    """
    Fills orders at the latest market price without delay.
    """

    def __init__(
        self,
        slippage: float = 0.0,
        commission: float = 0.0,
        partial_fill_ratio: float | None = None,
        max_staleness: float | None = None,
    ) -> None:
        super().__init__()
        self.slippage = slippage
        self.commission = commission
        self.partial_fill_ratio = partial_fill_ratio
        self.max_staleness = max_staleness
        self._prices: Dict[str, float] = {}
        self._timestamps: Dict[str, datetime] = {}
        self._sequence = itertools.count(1)

    def on_start(self) -> None:
        self.bus.subscribe(MarketEvent, self._cache_price)

    def on_stop(self) -> None:
        self.bus.unsubscribe(MarketEvent, self._cache_price)

    def _cache_price(self, event: MarketEvent) -> None:
        self._prices[event.symbol] = event.fields["close"]
        self._timestamps[event.symbol] = event.timestamp

    def on_order(self, event: OrderEvent) -> None:
        last_price = self._prices.get(event.symbol)
        if last_price is None:
            raise RuntimeError(f"No market data for symbol {event.symbol}")

        if self.max_staleness is not None:
            last_ts = self._timestamps.get(event.symbol)
            if last_ts is None or (event.timestamp - last_ts).total_seconds() > self.max_staleness:
                raise RuntimeError(f"Stale market data for symbol {event.symbol}")

        is_buy = event.direction == OrderSide.BUY
        qty = event.quantity
        if self.partial_fill_ratio is not None:
            qty = max(1, int(event.quantity * self.partial_fill_ratio))
        signed_qty = qty if is_buy else -qty
        price_adjustment = self.slippage if is_buy else -self.slippage
        fill_price = last_price + price_adjustment

        fill_event = FillEvent(
            timestamp=event.timestamp,
            order_id=f"{event.symbol}-{next(self._sequence)}",
            symbol=event.symbol,
            quantity=signed_qty,
            fill_price=fill_price,
            commission=self.commission,
            meta={"partial_fill_ratio": self.partial_fill_ratio or 1.0, "slippage": self.slippage},
        )
        self.bus.publish(fill_event)
