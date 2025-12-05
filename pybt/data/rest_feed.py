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
from pybt.errors import FeedError


class RESTPollingFeed(DataFeed):
    def __init__(
        self,
        symbol: str,
        url: str,
        poll_interval: float = 1.0,
        max_ticks: Optional[int] = None,
        fetcher: Optional[Callable[[str], dict]] = None,
        max_retries: int = 3,
        backoff_seconds: float = 0.5,
    ) -> None:
        super().__init__()
        if requests is None and fetcher is None:
            raise FeedError("RESTPollingFeed requires requests or a custom fetcher")
        self.symbol = symbol
        self.url = url
        self.poll_interval = poll_interval
        self.max_ticks = max_ticks
        self._ticks = 0
        self._last_price: Optional[float] = None
        self._fetcher = fetcher
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._sleep = time.sleep

    def prime(self) -> None:
        self._ticks = 0
        self._last_price = None

    def has_next(self) -> bool:
        if self.max_ticks is None:
            return True
        return self._ticks < self.max_ticks

    def next(self) -> None:
        # Fetcher supplies quotes; this feed owns retry/backoff and emits MarketEvent bars.
        quote = self._retry_fetch()
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
        self._sleep(self.poll_interval)

    def _fetch_quote(self) -> dict:
        if self._fetcher is not None:
            return self._fetcher(self.url)
        resp = requests.get(self.url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if "price" not in data:
            raise FeedError("REST response missing 'price'")
        return data

    def _retry_fetch(self) -> dict:
        attempts = 0
        last_exc: Exception | None = None
        # Exponential backoff protects downstream consumers from tight retry loops.
        while attempts <= self.max_retries:
            try:
                return self._fetch_quote()
            except Exception as exc:  # pragma: no cover - errors are tested separately
                last_exc = exc
                if attempts == self.max_retries:
                    break
                delay = self.backoff_seconds * (2 ** attempts)
                self._sleep(delay)
                attempts += 1
        raise FeedError(f"Failed to fetch REST quote after {self.max_retries + 1} attempts") from last_exc


__all__ = ["RESTPollingFeed"]
