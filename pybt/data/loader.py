
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional

from .bar import Bar


@dataclass
class DataSpec:
    path: Path
    date_col: str = "date"
    open_col: str = "open"
    high_col: str = "high"
    low_col: str = "low"
    close_col: str = "close"
    volume_col: str = "volume"
    date_format: Optional[str] = None  # e.g. "%Y-%m-%d"


def load_csv(spec: DataSpec) -> List[Bar]:
    """Load OHLCV bars from a CSV file.

    The CSV must have columns matching the spec. Extra columns are ignored.
    """
    bars: List[Bar] = []
    with spec.path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt_raw = row[spec.date_col]
            dt = (
                datetime.strptime(dt_raw, spec.date_format)
                if spec.date_format
                else _auto_parse_date(dt_raw)
            )
            bars.append(
                Bar(
                    dt=dt,
                    open=float(row[spec.open_col]),
                    high=float(row[spec.high_col]),
                    low=float(row[spec.low_col]),
                    close=float(row[spec.close_col]),
                    volume=float(row.get(spec.volume_col, 0.0) or 0.0),
                )
            )
    bars.sort(key=lambda b: b.dt)
    return bars


def _auto_parse_date(s: str) -> datetime:
    # Try common formats; fall back to ISO parser
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    # Last resort: datetime.fromisoformat (Python 3.11 handles many variants)
    try:
        return datetime.fromisoformat(s)
    except Exception:
        raise ValueError(f"Unrecognized date format: {s}")


def generate_synthetic(days: int = 500, start: Optional[datetime] = None) -> List[Bar]:
    """Generate a synthetic trending series for quick demos/tests."""
    start = start or datetime(2020, 1, 1)
    bars: List[Bar] = []
    price = 100.0
    drift = 0.0005
    vol = 0.01
    import random

    rng = random.Random(42)
    for i in range(days):
        dt = start + timedelta(days=i)
        # Geometric random walk with slight drift
        ret = drift + vol * (rng.random() - 0.5)
        new_price = max(1e-6, price * (1.0 + ret))
        high = max(price, new_price) * (1.0 + 0.002)
        low = min(price, new_price) * (1.0 - 0.002)
        volume = 1_000 + 200 * rng.random()
        bars.append(Bar(dt=dt, open=price, high=high, low=low, close=new_price, volume=volume))
        price = new_price
    return bars
