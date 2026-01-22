import itertools
from datetime import datetime
from enum import Enum
from typing import Dict, List

from pybt.core.enums import OrderSide
from pybt.core.events import FillEvent, MarketEvent, OrderEvent
from pybt.core.interfaces import ExecutionHandler
from pybt.errors import ExecutionError


class FillTiming(str, Enum):
    """Fill timing mode for execution handler.

    CURRENT_CLOSE: Fill at current bar's close price (default, has look-ahead bias).
    NEXT_OPEN: Queue order and fill at next bar's open price (realistic).
    """

    CURRENT_CLOSE = "current_close"
    NEXT_OPEN = "next_open"


class ImmediateExecutionHandler(ExecutionHandler):
    """
    Fills orders at market price with configurable timing.

    By default (fill_timing=CURRENT_CLOSE), fills at the current bar's close price.
    This is fast but has look-ahead bias since the signal was generated using
    the same close price.

    For more realistic backtesting, use fill_timing=NEXT_OPEN which queues
    orders and fills them at the next bar's open price.
    """

    def __init__(
        self,
        slippage: float = 0.0,
        commission: float = 0.0,
        partial_fill_ratio: float | None = None,
        max_staleness: float | None = None,
        fill_timing: FillTiming | str = FillTiming.CURRENT_CLOSE,
    ) -> None:
        super().__init__()
        self.slippage = slippage
        self.commission = commission
        self.partial_fill_ratio = partial_fill_ratio
        self.max_staleness = max_staleness
        if isinstance(fill_timing, str):
            fill_timing = FillTiming(fill_timing)
        self.fill_timing = fill_timing
        self._prices: Dict[str, float] = {}
        self._open_prices: Dict[str, float] = {}
        self._timestamps: Dict[str, datetime] = {}
        self._sequence = itertools.count(1)
        self._pending_orders: List[OrderEvent] = []

    def on_start(self) -> None:
        self.bus.subscribe(MarketEvent, self._cache_price)

    def on_stop(self) -> None:
        self.bus.unsubscribe(MarketEvent, self._cache_price)

    def _cache_price(self, event: MarketEvent) -> None:
        if self.fill_timing == FillTiming.NEXT_OPEN and self._pending_orders:
            open_price = event.fields.get("open")
            if open_price is not None:
                self._fill_pending_orders(event.symbol, open_price, event.timestamp)

        self._prices[event.symbol] = event.fields["close"]
        self._open_prices[event.symbol] = event.fields.get(
            "open", event.fields["close"]
        )
        self._timestamps[event.symbol] = event.timestamp

    def _fill_pending_orders(
        self, symbol: str, open_price: float, timestamp: datetime
    ) -> None:
        remaining: List[OrderEvent] = []
        for order in self._pending_orders:
            if order.symbol == symbol:
                self._execute_fill(order, open_price, timestamp)
            else:
                remaining.append(order)
        self._pending_orders = remaining

    def _execute_fill(
        self, order: OrderEvent, base_price: float, timestamp: datetime
    ) -> None:
        is_buy = order.direction == OrderSide.BUY
        qty = order.quantity
        if self.partial_fill_ratio is not None:
            qty = max(1, int(order.quantity * self.partial_fill_ratio))
        signed_qty = qty if is_buy else -qty
        price_adjustment = self.slippage if is_buy else -self.slippage
        fill_price = base_price + price_adjustment

        fill_event = FillEvent(
            timestamp=timestamp,
            order_id=f"{order.symbol}-{next(self._sequence)}",
            symbol=order.symbol,
            quantity=signed_qty,
            fill_price=fill_price,
            commission=self.commission,
            meta={
                "partial_fill_ratio": self.partial_fill_ratio or 1.0,
                "slippage": self.slippage,
            },
        )
        self.bus.publish(fill_event)

    def on_order(self, event: OrderEvent) -> None:
        last_price = self._prices.get(event.symbol)
        if last_price is None:
            raise ExecutionError(f"No market data for symbol {event.symbol}")

        if self.max_staleness is not None:
            last_ts = self._timestamps.get(event.symbol)
            if (
                last_ts is None
                or (event.timestamp - last_ts).total_seconds() > self.max_staleness
            ):
                raise ExecutionError(f"Stale market data for symbol {event.symbol}")

        if self.fill_timing == FillTiming.NEXT_OPEN:
            self._pending_orders.append(event)
            return

        self._execute_fill(event, last_price, event.timestamp)
