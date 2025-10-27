from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from .events import MarketEvent


@dataclass(frozen=True)
class Bar:
    """
    Simple OHLCV bar representation used by the in-memory data feed.
    """

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def as_event(self) -> MarketEvent:
        """
        Convert the bar into a market event.
        """

        fields: Mapping[str, float] = {
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }
        return MarketEvent(timestamp=self.timestamp, symbol=self.symbol, fields=fields)
