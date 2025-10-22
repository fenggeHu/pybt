from typing import Optional

from pybt.data.bar import Bar
from pybt.indicators.basic import SMA
from .base import Signal, Strategy


class SmaCrossStrategy(Strategy):
    def __init__(self, fast: int = 10, slow: int = 30, allow_short: bool = False):
        assert fast < slow, "fast must be < slow"
        self.fast = SMA(fast)
        self.slow = SMA(slow)
        self.allow_short = allow_short
        self._last_state: Optional[int] = None  # -1 short, 0 flat, 1 long

    def on_bar(self, bar: Bar) -> Optional[Signal]:
        f = self.fast.update(bar.close)
        s = self.slow.update(bar.close)
        if f is None or s is None:
            return None
        state = 1 if f > s else (-1 if (self.allow_short and f < s) else 0)
        if state == self._last_state:
            return None  # no change
        self._last_state = state
        return Signal(target_units=state)
