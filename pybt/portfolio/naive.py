from collections import defaultdict
from typing import DefaultDict, Dict

from pybt.core.enums import OrderSide, OrderType, SignalDirection
from pybt.core.events import FillEvent, MarketEvent, OrderEvent, SignalEvent
from pybt.core.interfaces import Portfolio


class NaivePortfolio(Portfolio):
    """
    Minimal portfolio translating signals into fixed-size market orders.
    """

    def __init__(self, lot_size: int = 100, initial_cash: float = 100_000.0) -> None:
        super().__init__()
        if lot_size <= 0:
            raise ValueError("lot_size must be positive.")
        self.lot_size = lot_size
        self.initial_cash = initial_cash
        self._positions: DefaultDict[str, int] = defaultdict(int)
        self._cash: float = initial_cash
        self._last_price: Dict[str, float] = {}

    def on_start(self) -> None:
        self._positions.clear()
        self._cash = self.initial_cash
        self._last_price.clear()

        # Subscribe for mark-to-market updates.
        self.bus.subscribe(MarketEvent, self._on_market_event)

    def on_stop(self) -> None:
        self.bus.unsubscribe(MarketEvent, self._on_market_event)

    def equity(self) -> float:
        """
        Current marked-to-market equity.
        """

        inventory_value = sum(self._positions[symbol] * self._last_price.get(symbol, 0.0) for symbol in self._positions)
        return self._cash + inventory_value

    def on_signal(self, event: SignalEvent) -> None:
        symbol = event.symbol
        position = self._positions[symbol]

        if event.direction == SignalDirection.LONG and position >= self.lot_size:
            return
        if event.direction == SignalDirection.SHORT and position <= -self.lot_size:
            return

        target_position = 0
        if event.direction == SignalDirection.LONG:
            target_position = self.lot_size
        elif event.direction == SignalDirection.SHORT:
            target_position = -self.lot_size
        elif event.direction == SignalDirection.EXIT:
            target_position = 0
        else:
            return

        delta = target_position - position
        if delta == 0:
            return

        direction = OrderSide.BUY if delta > 0 else OrderSide.SELL
        order = OrderEvent(
            timestamp=event.timestamp,
            symbol=symbol,
            quantity=abs(delta),
            order_type=OrderType.MARKET,
            direction=direction,
        )
        self.bus.publish(order)

    def on_fill(self, event: FillEvent) -> None:
        signed_quantity = event.quantity
        self._positions[event.symbol] += signed_quantity
        self._cash -= event.fill_price * signed_quantity
        self._cash -= event.commission

    def _on_market_event(self, event: MarketEvent) -> None:
        self._last_price[event.symbol] = event.fields["close"]
