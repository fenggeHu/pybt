from collections import defaultdict
from dataclasses import replace
from typing import DefaultDict

from pybt.core.enums import OrderSide
from pybt.core.events import FillEvent, OrderEvent
from pybt.core.interfaces import RiskManager


class MaxPositionRisk(RiskManager):
    """
    Caps the absolute position size per symbol.
    """

    def __init__(self, limit: int) -> None:
        super().__init__()
        if limit <= 0:
            raise ValueError("limit must be positive.")
        self.limit = limit
        self._positions: DefaultDict[str, int] = defaultdict(int)

    def on_start(self) -> None:
        self._positions.clear()
        self.bus.subscribe(FillEvent, self._on_fill)

    def on_stop(self) -> None:
        self.bus.unsubscribe(FillEvent, self._on_fill)

    def _on_fill(self, event: FillEvent) -> None:
        self._positions[event.symbol] += event.quantity

    def review(self, order: OrderEvent) -> OrderEvent | None:
        current = self._positions[order.symbol]
        is_buy = order.direction == OrderSide.BUY
        signed_qty = order.quantity if is_buy else -order.quantity

        if is_buy:
            available = self.limit - current
        else:
            available = self.limit + current  # short exposure

        if available <= 0:
            return None

        adjusted_quantity = min(abs(signed_qty), available)
        if adjusted_quantity <= 0:
            return None

        if adjusted_quantity == abs(signed_qty):
            return order

        return replace(order, quantity=adjusted_quantity)
