from collections import deque
from statistics import mean, pstdev
from typing import Deque

from pybt.core.enums import Exposure, SignalDirection
from pybt.core.events import MarketEvent, SignalEvent
from pybt.core.interfaces import Strategy


class UptrendBreakoutStrategy(Strategy):
    """简单的上升趋势突破策略。

    当价格突破均值上轨（均值 + breakout_factor * 标准差）时做多，
    当价格回落到均值下方时平仓。仅做多/平仓，不做空。
    """

    def __init__(
        self,
        symbol: str,
        window: int = 20,
        breakout_factor: float = 1.5,
        strategy_id: str = "uptrend",
    ) -> None:
        super().__init__()
        if window <= 1:
            raise ValueError("window must be greater than 1")
        if breakout_factor <= 0:
            raise ValueError("breakout_factor must be positive")
        self.symbol = symbol
        self.window = window
        self.breakout_factor = breakout_factor
        self.strategy_id = strategy_id
        self._prices: Deque[float] = deque(maxlen=window)
        self._exposure: Exposure = Exposure.FLAT

    def on_start(self) -> None:
        self._prices.clear()
        self._exposure = Exposure.FLAT

    def on_market(self, event: MarketEvent) -> None:
        if event.symbol != self.symbol:
            return

        price = event.fields["close"]
        self._prices.append(price)

        if len(self._prices) < self.window:
            return

        avg = mean(self._prices)
        volatility = pstdev(self._prices) if len(self._prices) > 1 else 0.0
        threshold = avg + self.breakout_factor * volatility

        direction: SignalDirection | None = None

        if price >= threshold and self._exposure != Exposure.LONG:
            direction = SignalDirection.LONG
            self._exposure = Exposure.LONG
        elif price < avg and self._exposure == Exposure.LONG:
            direction = SignalDirection.EXIT
            self._exposure = Exposure.FLAT

        if direction is None:
            return

        strength = max(price - threshold, 0.0) if direction == SignalDirection.LONG else max(threshold - price, 0.0)
        signal = SignalEvent(
            timestamp=event.timestamp,
            strategy_id=self.strategy_id,
            symbol=self.symbol,
            direction=direction,
            strength=strength,
        )
        self.bus.publish(signal)
