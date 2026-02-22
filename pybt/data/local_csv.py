"""Local CSV/Parquet daily bar feed for `.tibet/{market}/features/{symbol}/Bar.csv`."""

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, cast

try:
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    pd = None

from pybt.core.interfaces import DataFeed
from pybt.core.models import Bar
from pybt.errors import DataError


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
    _validate_monotonic(bars, source=str(path))
    return bars


def load_bars_from_parquet(
    path: Path,
    *,
    symbol: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> List[Bar]:
    """Load bars from a Parquet file with the same schema as CSV (requires pandas)."""
    try:
        import pandas as pd_local  # type: ignore
    except ImportError as exc:
        raise ImportError("pandas is required to read Parquet files") from exc
    symbol = symbol or _infer_symbol(path)
    df = cast(Any, pd_local.read_parquet(path))
    required = {"date", "open", "high", "low", "close", "volume"}
    missing = required - set(cast(Any, df).columns)
    if missing:
        raise ValueError(f"Parquet missing required columns: {missing}")
    date_col = cast(Any, pd_local.to_datetime(cast(Any, df)["date"], errors="coerce"))
    if cast(Any, date_col).isna().any():
        raise ValueError("Parquet 'date' contains invalid datetime values")
    if hasattr(cast(Any, date_col).dt, "tz") and cast(Any, date_col).dt.tz is not None:
        date_col = cast(Any, date_col).dt.tz_localize(None)
    df = cast(Any, df).assign(date=date_col)
    if start is not None:
        df = cast(Any, df)[cast(Any, df)["date"] >= start]
    if end is not None:
        df = cast(Any, df)[cast(Any, df)["date"] <= end]

    records = cast(List[dict[str, Any]], cast(Any, df).to_dict(orient="records"))
    bars: List[Bar] = []
    for row in records:
        bars.append(
            Bar(
                symbol=symbol,
                timestamp=_parse_timestamp(str(row["date"])),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume", 0.0) or 0.0),
                amount=float(row.get("amount", 0.0) or 0.0),
            )
        )
    bars.sort(key=lambda b: b.timestamp)
    _validate_monotonic(bars, source=str(path))
    return bars


def _validate_monotonic(bars: List[Bar], source: str) -> None:
    for i in range(1, len(bars)):
        if bars[i].timestamp < bars[i - 1].timestamp:
            raise DataError(f"Bars not sorted by timestamp in {source}")


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
        self._idx: int = 0
        self._primed: bool = False

    def _load(self) -> List[Bar]:
        suffix = self._path.suffix.lower()
        if suffix == ".csv":
            return load_bars_from_csv(
                self._path, symbol=self._symbol, start=self._start, end=self._end
            )
        if suffix in {".parquet", ".pq"}:
            return load_bars_from_parquet(
                self._path, symbol=self._symbol, start=self._start, end=self._end
            )
        raise ValueError(
            f"Unsupported bar file extension: '{self._path.suffix}'. Expected .csv or .parquet"
        )

    def prime(self) -> None:
        self._idx = 0
        self._primed = True

    def has_next(self) -> bool:
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
