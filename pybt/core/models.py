from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from .events import MarketEvent


@dataclass(frozen=True)
class Bar:
    """
    Simple OHLCVA bar representation used by the in-memory data feed.
    
    Attributes:
        symbol: 股票代码
        timestamp: 时间戳
        open: 开盘价
        high: 最高价
        low: 最低价
        close: 收盘价
        volume: 成交量
        amount: 成交额
    """

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    amount: float = 0.0

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
            "amount": self.amount,
        }
        return MarketEvent(timestamp=self.timestamp, symbol=self.symbol, fields=fields)
