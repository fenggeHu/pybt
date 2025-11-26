"""Local CSV/Parquet daily bar feed for `.tibet/{market}/features/{symbol}/Bar.csv`."""

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional, Sequence

try:
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    pd = None

from pybt.core.events import MarketEvent
from pybt.core.interfaces import DataFeed
from pybt.core.models import Bar


def _parse_timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.strptime(value, "%Y-%m-%d")


def _infer_symbol(path: Path) -> str:
    # Expect structure .../{symbol}/Bar.csv
    return path.parent.name


def load_bars_from_csv(
    path: Path,
    *,
    symbol: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> List[Bar]:
    """Load bars from a CSV file with columns: date, open, high, low, close, volume[, amount]."""
    symbol = symbol or _infer_symbol(path)
    bars: List[Bar] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"date", "open", "high", "low", "close", "volume"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV missing required columns: {missing}")
        for row in reader:
            ts = _parse_timestamp(row["date"])
            if start and ts < start:
                continue
            if end and ts > end:
                continue
            bars.append(
                Bar(
                    symbol=symbol,
                    timestamp=ts,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0.0)),
                    amount=float(row.get("amount", 0.0)) if row.get("amount") else 0.0,
                )
            )
    bars.sort(key=lambda b: b.timestamp)
    return bars


def load_bars_from_parquet(
    path: Path,
    *,
    symbol: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> List[Bar]:
    """Load bars from a Parquet file with the same schema as CSV (requires pandas)."""
    if pd is None:
        raise ImportError("pandas is required to read Parquet files")
    symbol = symbol or _infer_symbol(path)
    df = pd.read_parquet(path)  # type: ignore
    required = {"date", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Parquet missing required columns: {missing}")
    if start is not None:
        df = df[df["date"] >= start]
    if end is not None:
        df = df[df["date"] <= end]
    bars = [
        Bar(
            symbol=symbol,
            timestamp=_parse_timestamp(str(row["date"])),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row.get("volume", 0.0)),
            amount=float(row.get("amount", 0.0)) if "amount" in row else 0.0,
        )
        for _, row in df.iterrows()
    ]
    bars.sort(key=lambda b: b.timestamp)
    return bars


class LocalCSVBarFeed(DataFeed):
    """
    Deterministic data feed backed by a local CSV/Parquet daily bar file.
    """

    def __init__(
        self,
        path: Path,
        *,
        symbol: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> None:
        super().__init__()
        self._path = path
        self._symbol = symbol or _infer_symbol(path)
        self._start = start
        self._end = end
        self._bars: List[Bar] = self._load()
        self._iterator: Iterator[Bar] | None = None
        self._buffer: List[MarketEvent] = []

    def _load(self) -> List[Bar]:
        if self._path.suffix.lower() == ".csv":
            return load_bars_from_csv(self._path, symbol=self._symbol, start=self._start, end=self._end)
        return load_bars_from_parquet(self._path, symbol=self._symbol, start=self._start, end=self._end)

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
