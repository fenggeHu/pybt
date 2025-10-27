import time
from datetime import datetime
from typing import Optional

try:
    import adata  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    adata = None

from pybt.core.interfaces import DataFeed
from pybt.core.models import Bar


class ADataLiveFeed(DataFeed):
    """
    Polls the AData SDK for live quotes and emits market events.
    """

    def __init__(
        self,
        symbol: str,
        poll_interval: float = 1.0,
        max_ticks: Optional[int] = None,
    ) -> None:
        super().__init__()
        if adata is None:
            raise ImportError(
                "ADataLiveFeed requires the 'adata' package. Install it via 'pip install adata'."
            )
        self.symbol = symbol
        self.poll_interval = poll_interval
        self.max_ticks = max_ticks
        self._ticks = 0
        self._last_price: Optional[float] = None

    def prime(self) -> None:
        self._ticks = 0
        self._last_price = None

    def has_next(self) -> bool:
        if self.max_ticks is None:
            return True
        return self._ticks < self.max_ticks

    def next(self) -> None:
        quote = self._fetch_quote()
        price = quote["price"]
        timestamp = datetime.utcnow()
        last = self._last_price or price
        high = max(price, last)
        low = min(price, last)
        bar = Bar(
            symbol=self.symbol,
            timestamp=timestamp,
            open=last,
            high=high,
            low=low,
            close=price,
            volume=float(quote.get("volume", 0.0)),
        )
        self._last_price = price
        self._ticks += 1
        self.bus.publish(bar.as_event())
        time.sleep(self.poll_interval)

    def _fetch_quote(self) -> dict:
        df = adata.stock.market.list_market_current(code_list=[self.symbol])
        if df.empty:
            raise RuntimeError(f"adata returned no data for {self.symbol}")
        row = df.iloc[0]
        return {
            "price": float(row["price"]),
            "volume": float(row.get("volume", 0.0)),
        }
