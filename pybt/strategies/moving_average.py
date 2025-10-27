from collections import deque
from statistics import mean
from typing import Deque

from pybt.core.enums import Exposure, SignalDirection
from pybt.core.events import MarketEvent, SignalEvent
from pybt.core.interfaces import Strategy


class MovingAverageCrossStrategy(Strategy):
    """
    Classic moving-average crossover example strategy.
    """

    def __init__(
            self,
            symbol: str,
            short_window: int = 20,
            long_window: int = 50,
            strategy_id: str = "mac",
    ) -> None:
        super().__init__()
        if short_window >= long_window:
            raise ValueError("short_window must be less than long_window.")
        self.symbol = symbol
        self.short_window = short_window
        self.long_window = long_window
        self.strategy_id = strategy_id
        self._prices: Deque[float] = deque(maxlen=long_window)
        self._exposure: Exposure = Exposure.FLAT

    def on_start(self) -> None:
        self._prices.clear()
        self._exposure = Exposure.FLAT

    def on_market(self, event: MarketEvent) -> None:
        if event.symbol != self.symbol:
            return
        price = event.fields["close"]
        self._prices.append(price)
        if len(self._prices) < self.long_window:
            return

        short_ma = mean(list(self._prices)[-self.short_window:])
        long_ma = mean(self._prices)

        direction: SignalDirection | None = None
        if short_ma > long_ma and self._exposure != Exposure.LONG:
            direction = SignalDirection.LONG
            self._exposure = Exposure.LONG
        elif short_ma < long_ma and self._exposure != Exposure.SHORT:
            direction = SignalDirection.SHORT
            self._exposure = Exposure.SHORT

        if direction is None:
            return

        signal = SignalEvent(
            timestamp=event.timestamp,
            strategy_id=self.strategy_id,
            symbol=self.symbol,
            direction=direction,
            strength=abs(short_ma - long_ma),
        )
        self.bus.publish(signal)
