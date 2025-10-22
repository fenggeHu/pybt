from collections import deque
from typing import Deque, Iterable, List, Optional


class SMA:
    """Simple Moving Average for streaming usage.

    Keeps a fixed window; `update(x)` returns current SMA after adding x.
    """

    def __init__(self, period: int):
        assert period >= 1
        self.period = period
        self.buf: Deque[float] = deque()
        self.sum: float = 0.0

    def update(self, x: float) -> Optional[float]:
        self.buf.append(x)
        self.sum += x
        if len(self.buf) > self.period:
            self.sum -= self.buf.popleft()
        if len(self.buf) < self.period:
            return None
        return self.sum / self.period

    @staticmethod
    def series(values: Iterable[float], period: int) -> List[Optional[float]]:
        sma = SMA(period)
        out: List[Optional[float]] = []
        for v in values:
            out.append(sma.update(v))
        return out


class EMA:
    def __init__(self, period: int):
        assert period >= 1
        self.period = period
        self.mult = 2.0 / (period + 1)
        self.value: Optional[float] = None

    def update(self, x: float) -> float:
        self.value = x if self.value is None else (x - self.value) * self.mult + self.value
        return self.value

    @staticmethod
    def series(values: Iterable[float], period: int) -> List[Optional[float]]:
        ema = EMA(period)
        out: List[Optional[float]] = []
        for v in values:
            out.append(ema.update(v))
        return out
