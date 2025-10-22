from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from .bar import Bar


@dataclass
class FeedEvent:
    dt_iso: str
    items: List[Tuple[str, Bar]]  # list of (symbol, Bar) present at this dt


class DataFeed:
    """Simple multi-symbol daily feed that merges bars by datetime.

    Assumes each symbol has a list of Bars sorted by dt ascending.
    """

    def __init__(self, data_by_symbol: Dict[str, List[Bar]]):
        self.data_by_symbol = {s: list(bs) for s, bs in data_by_symbol.items()}
        self._dt_index: Dict[str, int] = {s: 0 for s in data_by_symbol}

        # Build the sorted unique union of all datetimes
        dts = set()
        for bs in data_by_symbol.values():
            for b in bs:
                dts.add(b.dt)
        self.timeline = sorted(dts)

    def __iter__(self):
        latest: Dict[str, Bar] = {}
        for dt in self.timeline:
            items: List[Tuple[str, Bar]] = []
            for sym, bars in self.data_by_symbol.items():
                idx = self._dt_index[sym]
                # Consume bars up to current dt (should be at most 1 if well-formed daily series)
                while idx < len(bars) and bars[idx].dt <= dt:
                    latest[sym] = bars[idx]
                    idx += 1
                self._dt_index[sym] = idx
                b = latest.get(sym)
                if b is not None and b.dt == dt:
                    items.append((sym, b))
            if items:
                yield FeedEvent(dt_iso=dt.isoformat(), items=items)

