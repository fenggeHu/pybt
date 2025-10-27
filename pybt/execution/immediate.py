from __future__ import annotations

import itertools
from typing import Dict

from pybt.core.enums import OrderSide
from pybt.core.events import FillEvent, MarketEvent, OrderEvent
from pybt.core.interfaces import ExecutionHandler


class ImmediateExecutionHandler(ExecutionHandler):
    """
    Fills orders at the latest market price without delay.
    """

    def __init__(self, slippage: float = 0.0, commission: float = 0.0) -> None:
        super().__init__()
        self.slippage = slippage
        self.commission = commission
        self._prices: Dict[str, float] = {}
        self._sequence = itertools.count(1)

    def on_start(self) -> None:
        self.bus.subscribe(MarketEvent, self._cache_price)

    def on_stop(self) -> None:
        self.bus.unsubscribe(MarketEvent, self._cache_price)

    def _cache_price(self, event: MarketEvent) -> None:
        self._prices[event.symbol] = event.fields["close"]

    def on_order(self, event: OrderEvent) -> None:
        last_price = self._prices.get(event.symbol)
        if last_price is None:
            raise RuntimeError(f"No market data for symbol {event.symbol}")

        is_buy = event.direction == OrderSide.BUY
        signed_qty = event.quantity if is_buy else -event.quantity
        price_adjustment = self.slippage if is_buy else -self.slippage
        fill_price = last_price + price_adjustment

        fill_event = FillEvent(
            timestamp=event.timestamp,
            order_id=f"{event.symbol}-{next(self._sequence)}",
            symbol=event.symbol,
            quantity=signed_qty,
            fill_price=fill_price,
            commission=self.commission,
        )
        self.bus.publish(fill_event)
