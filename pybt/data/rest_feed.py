"""Generic polling REST live feed.

Fetches price data from a REST endpoint or custom fetcher function and emits
MarketEvent slices. Designed for testing and extension; production users should
inject a hardened fetcher with retries and auth.
"""

import time
from datetime import datetime
from typing import Callable, Optional

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    requests = None

from pybt.core.interfaces import DataFeed
from pybt.core.models import Bar


class RESTPollingFeed(DataFeed):
    def __init__(
        self,
        symbol: str,
        url: str,
        poll_interval: float = 1.0,
        max_ticks: Optional[int] = None,
        fetcher: Optional[Callable[[str], dict]] = None,
    ) -> None:
        super().__init__()
        if requests is None and fetcher is None:
            raise ImportError("RESTPollingFeed requires requests or a custom fetcher")
        self.symbol = symbol
        self.url = url
        self.poll_interval = poll_interval
        self.max_ticks = max_ticks
        self._ticks = 0
        self._last_price: Optional[float] = None
        self._fetcher = fetcher

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
        ts = datetime.utcnow()
        last = self._last_price or price
        high = max(price, last)
        low = min(price, last)
        bar = Bar(
            symbol=self.symbol,
            timestamp=ts,
            open=last,
            high=high,
            low=low,
            close=price,
            volume=float(quote.get("volume", 0.0)),
            amount=float(quote.get("amount", 0.0)),
        )
        self._last_price = price
        self._ticks += 1
        self.bus.publish(bar.as_event())
        time.sleep(self.poll_interval)

    def _fetch_quote(self) -> dict:
        if self._fetcher is not None:
            return self._fetcher(self.url)
        resp = requests.get(self.url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if "price" not in data:
            raise RuntimeError("REST response missing 'price'")
        return data


__all__ = ["RESTPollingFeed"]
