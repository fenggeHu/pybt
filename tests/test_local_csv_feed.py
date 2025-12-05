from datetime import datetime
from pathlib import Path

import pytest

from pybt.data.local_csv import LocalCSVBarFeed, load_bars_from_csv


CSV_CONTENT = """date,open,high,low,close,volume,amount
2024-01-01,10,11,9,10.5,1000,10000
2024-01-02,10.5,11.5,10,11,1200,13200
2024-01-03,11,12,10.5,11.8,1500,17700
"""


def _write_csv(tmp_path: Path) -> Path:
    path = tmp_path / "AAA" / "Bar.csv"
    path.parent.mkdir(parents=True)
    path.write_text(CSV_CONTENT, encoding="utf-8")
    return path


def test_load_bars_from_csv_respects_bounds(tmp_path: Path) -> None:
    path = _write_csv(tmp_path)
    start = datetime(2024, 1, 2)
    end = datetime(2024, 1, 3)
    bars = load_bars_from_csv(path, start=start, end=end)
    assert len(bars) == 2
    assert bars[0].timestamp == datetime(2024, 1, 2)
    assert bars[-1].timestamp == datetime(2024, 1, 3)


def test_local_csv_feed_iterates(tmp_path: Path) -> None:
    path = _write_csv(tmp_path)
    feed = LocalCSVBarFeed(path)
    feed.bind(object())  # bus will be set later

    from pybt.core.event_bus import EventBus
    from pybt.core.events import MarketEvent

    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    while feed.has_next():
        feed.next()
        bus.dispatch()

    assert len(captured) == 3
    assert captured[0].fields["close"] == 10.5
