from collections import defaultdict
from typing import DefaultDict, Dict

from pybt.core.enums import OrderSide
from pybt.core.events import FillEvent, MarketEvent, OrderEvent
from pybt.core.interfaces import RiskManager


class ConcentrationRisk(RiskManager):
    """限制单一标的敞口占组合权益的比例。

    max_fraction 表示单标的市值上限 = max_fraction * equity。
    """

    def __init__(self, initial_cash: float, max_fraction: float = 0.5) -> None:
        super().__init__()
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive.")
        if not 0 < max_fraction <= 1:
            raise ValueError("max_fraction must be in (0, 1].")
        self.initial_cash = initial_cash
        self.max_fraction = max_fraction
        self._cash: float = initial_cash
        self._positions: DefaultDict[str, int] = defaultdict(int)
        self._prices: Dict[str, float] = {}

    def on_start(self) -> None:
        self._cash = self.initial_cash
        self._positions.clear()
        self._prices.clear()
        self.bus.subscribe(FillEvent, self._on_fill)
        self.bus.subscribe(MarketEvent, self._on_market)

    def on_stop(self) -> None:
        self.bus.unsubscribe(FillEvent, self._on_fill)
        self.bus.unsubscribe(MarketEvent, self._on_market)

    def _on_fill(self, event: FillEvent) -> None:
        self._positions[event.symbol] += event.quantity
        self._cash -= event.fill_price * event.quantity
        self._cash -= event.commission

    def _on_market(self, event: MarketEvent) -> None:
        self._prices[event.symbol] = event.fields["close"]

    def _equity(self) -> float:
        inventory = sum(self._positions[symbol] * self._prices.get(symbol, 0.0) for symbol in self._positions)
        return self._cash + inventory

    def review(self, order: OrderEvent) -> OrderEvent | None:
        price = self._prices.get(order.symbol)
        if price is None:
            return None

        # 卖单降低集中度，直接通过
        if order.direction == OrderSide.SELL:
            return order

        equity = self._equity()
        if equity <= 0:
            return None

        current_value = self._positions[order.symbol] * price
        max_value = self.max_fraction * equity
        remaining = max_value - current_value
        if remaining <= 0:
            return None

        desired_value = price * order.quantity
        if desired_value <= remaining:
            return order

        adjusted_qty = int(remaining // price)
        if adjusted_qty <= 0:
            return None

        return OrderEvent(
            timestamp=order.timestamp,
            symbol=order.symbol,
            quantity=adjusted_qty,
            order_type=order.order_type,
            direction=order.direction,
            limit_price=order.limit_price,
            stop_price=order.stop_price,
            meta=order.meta,
        )


__all__ = ["ConcentrationRisk"]
