from collections import defaultdict
from typing import DefaultDict, Dict

from pybt.core.enums import OrderSide
from pybt.core.events import FillEvent, MarketEvent, OrderEvent
from pybt.core.interfaces import RiskManager


class BuyingPowerRisk(RiskManager):
    """限制买单所需资金不超过可用买力，并可按可用买力自动缩量。

    采用简单杠杆模型：允许的最大总敞口 = max_leverage * equity。
    """

    def __init__(self, initial_cash: float, max_leverage: float = 1.0, reserve_cash: float = 0.0) -> None:
        super().__init__()
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive.")
        if max_leverage <= 0:
            raise ValueError("max_leverage must be positive.")
        if reserve_cash < 0:
            raise ValueError("reserve_cash cannot be negative.")
        self.initial_cash = initial_cash
        self.max_leverage = max_leverage
        self.reserve_cash = reserve_cash
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

    def _gross_exposure(self) -> float:
        return sum(abs(self._positions[symbol]) * self._prices.get(symbol, 0.0) for symbol in self._positions)

    def review(self, order: OrderEvent) -> OrderEvent | None:
        if order.direction == OrderSide.SELL:
            return order  # 卖单不受买力限制

        price = self._prices.get(order.symbol)
        if price is None:
            # 没有价格无法评估成本，拒绝执行
            return None

        equity = self._equity()
        gross = self._gross_exposure()
        max_gross = self.max_leverage * max(equity, 0.0)
        available_gross = max_gross - gross - self.reserve_cash
        if available_gross <= 0:
            return None

        desired_gross = price * order.quantity
        if desired_gross <= available_gross:
            return order

        adjusted_qty = int(available_gross // price)
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


__all__ = ["BuyingPowerRisk"]
