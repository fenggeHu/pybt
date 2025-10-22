from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Bar:
    """Single OHLCV bar.

    Keep this tiny so it can be used without heavy deps.
    """

    dt: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def mid(self) -> float:
        # Mid-price proxy; used by the naive broker
        return (self.high + self.low) / 2.0
