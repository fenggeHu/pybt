from typing import Iterator, List, Sequence

from pybt.core.events import MarketEvent
from pybt.core.interfaces import DataFeed
from pybt.core.models import Bar


class InMemoryBarFeed(DataFeed):
    """
    Deterministic data feed pushing preloaded bar data onto the bus.
    """

    def __init__(self, bars: Sequence[Bar]) -> None:
        super().__init__()
        self._bars: List[Bar] = sorted(bars, key=lambda bar: bar.timestamp)
        self._iterator: Iterator[Bar] | None = None
        self._buffer: List[MarketEvent] = []

    def prime(self) -> None:
        self._iterator = iter(self._bars)
        self._buffer.clear()

    def has_next(self) -> bool:
        if self._iterator is None:
            raise RuntimeError("Data feed not primed. Call prime() before iteration.")
        if self._buffer:
            return True
        try:
            bar = next(self._iterator)
        except StopIteration:
            return False
        self._buffer.append(bar.as_event())
        return True

    def next(self) -> None:
        if not self.has_next():
            return
        event = self._buffer.pop(0)
        self.bus.publish(event)
