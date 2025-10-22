from typing import Optional

from pybt.data.bar import Bar
from pybt.indicators.basic import SMA
from .base import Signal, Strategy


class SmaTrendWeightStrategy(Strategy):
    """Assigns portfolio weights based on SMA crossover direction.

    Parameters
    ----------
    symbol : str
        Symbol identifier (used only for readability/logging).
    fast : int
        Fast SMA period.
    slow : int
        Slow SMA period (must be > fast).
    long_weight : float
        Weight when fast > slow.
    short_weight : float
        Weight when fast < slow (ignored if allow_short=False via allocator).
    neutral_weight : float
        Weight when conditions are neutral (default 0).
    change_only : bool
        If True, emit signals only when weight changes (reduces redundant orders).
    """

    def __init__(
            self,
            symbol: str,
            fast: int = 10,
            slow: int = 30,
            long_weight: float = 0.5,
            short_weight: float = 0.0,
            neutral_weight: float = 0.0,
            change_only: bool = True,
    ):
        assert fast < slow, "fast must be < slow"
        self.symbol = symbol
        self.fast = SMA(fast)
        self.slow = SMA(slow)
        self.long_weight = float(long_weight)
        self.short_weight = float(short_weight)
        self.neutral_weight = float(neutral_weight)
        self.change_only = change_only
        self._last_weight: Optional[float] = None

    def on_bar(self, bar: Bar):
        f = self.fast.update(bar.close)
        s = self.slow.update(bar.close)
        if f is None or s is None:
            return None
        if f > s:
            weight = self.long_weight
        elif f < s:
            weight = self.short_weight
        else:
            weight = self.neutral_weight
        if self.change_only and self._last_weight is not None and abs(weight - self._last_weight) < 1e-9:
            return None
        self._last_weight = weight
        return Signal(target_weight=weight)
