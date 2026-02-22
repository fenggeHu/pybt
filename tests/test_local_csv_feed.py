from datetime import datetime
from pathlib import Path

import pytest

from pybt.data.local_csv import (
    LocalCSVBarFeed,
    load_bars_from_csv,
    load_bars_from_parquet,
)

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


def test_local_csv_feed_has_next_is_side_effect_free(tmp_path: Path) -> None:
    path = _write_csv(tmp_path)
    feed = LocalCSVBarFeed(path)

    from pybt.core.event_bus import EventBus
    from pybt.core.events import MarketEvent

    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    assert feed.has_next() is True
    assert feed.has_next() is True

    feed.next()
    bus.dispatch()
    assert len(captured) == 1
    assert captured[0].timestamp == datetime(2024, 1, 1)


def test_local_csv_feed_rejects_unsupported_suffix(tmp_path: Path) -> None:
    path = tmp_path / "AAA" / "Bar.txt"
    path.parent.mkdir(parents=True)
    path.write_text("dummy", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported bar file extension"):
        LocalCSVBarFeed(path)


def test_load_bars_from_parquet_converts_string_dates_before_filtering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "volume": 1000,
            },
            {
                "date": "2024-01-02",
                "open": 10.5,
                "high": 12,
                "low": 10,
                "close": 11,
                "volume": 1200,
            },
        ]
    )
    monkeypatch.setattr(pd, "read_parquet", lambda _path: df)

    bars = load_bars_from_parquet(
        tmp_path / "AAA" / "Bar.parquet",
        start=datetime(2024, 1, 2),
        end=datetime(2024, 1, 2),
    )
    assert len(bars) == 1
    assert bars[0].timestamp == datetime(2024, 1, 2)
