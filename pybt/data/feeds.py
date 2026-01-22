from typing import List, Sequence

from pybt.core.interfaces import DataFeed
from pybt.core.models import Bar
from pybt.errors import DataError


class InMemoryBarFeed(DataFeed):
    """
    Deterministic data feed pushing preloaded bar data onto the bus.
    """

    def __init__(self, bars: Sequence[Bar]) -> None:
        super().__init__()
        self._bars: List[Bar] = sorted(bars, key=lambda bar: bar.timestamp)
        self._validate_monotonic()
        self._idx: int = 0
        self._primed: bool = False

    def prime(self) -> None:
        self._idx = 0
        self._primed = True

    def has_next(self) -> bool:
        # Pure check: no iterator consumption/prefetch.
        if not self._primed:
            raise RuntimeError("Data feed not primed. Call prime() before iteration.")
        return self._idx < len(self._bars)

    def next(self) -> None:
        if not self._primed:
            raise RuntimeError("Data feed not primed. Call prime() before iteration.")
        if not self.has_next():
            return
        bar = self._bars[self._idx]
        self._idx += 1
        self.bus.publish(bar.as_event())

    def _validate_monotonic(self) -> None:
        for i in range(1, len(self._bars)):
            if self._bars[i].timestamp < self._bars[i - 1].timestamp:
                raise DataError("Bars must be sorted by timestamp")
