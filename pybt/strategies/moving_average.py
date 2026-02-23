from collections import deque
from statistics import mean
from typing import Deque

from pybt.core.enums import Exposure, SignalDirection
from pybt.core.events import MarketEvent, SignalEvent, StrategyDebugEvent
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
            debug_signal: bool = False,
    ) -> None:
        super().__init__()
        if short_window >= long_window:
            raise ValueError("short_window must be less than long_window.")
        self.symbol = symbol
        self.short_window = short_window
        self.long_window = long_window
        self.strategy_id = strategy_id
        self.debug_signal = debug_signal
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
            if self.debug_signal:
                self._emit_debug(
                    event=event,
                    stage="warmup",
                    message="insufficient bars",
                    details={
                        "price": price,
                        "bars_ready": len(self._prices),
                        "bars_required": self.long_window,
                    },
                )
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
            if self.debug_signal:
                self._emit_debug(
                    event=event,
                    stage="hold",
                    message="no crossover",
                    details={
                        "price": price,
                        "short_ma": short_ma,
                        "long_ma": long_ma,
                        "exposure": self._exposure.value,
                    },
                )
            return

        signal = SignalEvent(
            timestamp=event.timestamp,
            strategy_id=self.strategy_id,
            symbol=self.symbol,
            direction=direction,
            strength=abs(short_ma - long_ma),
            meta={"short_ma": short_ma, "long_ma": long_ma, "price": price},
        )
        self.bus.publish(signal)
        if self.debug_signal:
            self._emit_debug(
                event=event,
                stage="signal",
                message=f"emit {direction.value}",
                details={
                    "price": price,
                    "short_ma": short_ma,
                    "long_ma": long_ma,
                    "direction": direction.value,
                    "strength": signal.strength,
                },
            )

    def _emit_debug(
        self,
        *,
        event: MarketEvent,
        stage: str,
        message: str,
        details: dict[str, float | int | str],
    ) -> None:
        self.bus.publish(
            StrategyDebugEvent(
                timestamp=event.timestamp,
                strategy_id=self.strategy_id,
                symbol=self.symbol,
                stage=stage,
                message=message,
                details=details,
            )
        )
