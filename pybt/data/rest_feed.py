"""Generic polling REST live feed.

Fetches price data from a REST endpoint or custom fetcher function and emits
MarketEvent slices. Designed for testing and extension; production users should
inject a hardened fetcher with retries and auth.
"""

import time
import hashlib
import json
from datetime import datetime
from typing import Any, Callable, Mapping, Optional
from urllib.parse import urlencode

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
        if requests is None:
            raise FeedError("requests is required for RESTPollingFeed")
        resp = requests.get(self.url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if "price" not in data:
            raise FeedError("REST response missing 'price'")
        return data

    def _retry_fetch(self) -> dict:
        attempts = 0
        last_exc: Optional[Exception] = None
        # Exponential backoff protects downstream consumers from tight retry loops.
        while attempts <= self.max_retries:
            try:
                return self._fetch_quote()
            except Exception as exc:  # pragma: no cover - errors are tested separately
                last_exc = exc
                if attempts == self.max_retries:
                    break
                delay = self.backoff_seconds * (2**attempts)
                self._sleep(delay)
                attempts += 1
        raise FeedError(
            f"Failed to fetch REST quote after {self.max_retries + 1} attempts"
        ) from last_exc


def _extract_float(source: Mapping[str, Any], keys: tuple[str, ...]) -> Optional[float]:
    for key in keys:
        if key not in source:
            continue
        try:
            return float(source[key])
        except Exception:
            continue
    return None


class EastmoneySSEFeed(DataFeed):
    def __init__(
        self,
        symbol: str,
        *,
        sse_url: Optional[str] = None,
        secid: Optional[str] = None,
        token: str = "",
        cname: Optional[str] = None,
        seq: int = 0,
        noop: int = 0,
        parser: Optional[Callable[[str], Optional[dict[str, float]]]] = None,
        get_request: Optional[Callable[..., Any]] = None,
        max_ticks: Optional[int] = None,
        max_reconnects: int = 3,
        backoff_seconds: float = 0.5,
        connect_timeout: float = 5.0,
        read_timeout: float = 30.0,
        snapshot_url: str = "https://push2.eastmoney.com/api/qt/stock/get",
        snapshot_fields: str = "f43,f47,f48",
        snapshot_ut: str = "fa5fd1943c7b386f172d6893dbfba10b",
        price_scale: float = 100.0,
    ) -> None:
        super().__init__()
        if requests is None and get_request is None:
            raise FeedError("EastmoneySSEFeed requires requests or custom get_request")
        self.symbol = symbol
        self.sse_url = sse_url
        self.secid = secid or self._symbol_to_secid(symbol)
        self.token = token
        self.cname = cname or self._default_cname(symbol)
        self.seq = seq
        self.noop = noop
        self.parser = parser or self._default_parser
        self._get_request = get_request or requests.get  # type: ignore[attr-defined]
        self.max_ticks = max_ticks
        self.max_reconnects = max_reconnects
        self.backoff_seconds = backoff_seconds
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.snapshot_url = snapshot_url
        self.snapshot_fields = snapshot_fields
        self.snapshot_ut = snapshot_ut
        self.price_scale = price_scale
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
        attempts = 0
        last_exc: Optional[Exception] = None
        while attempts <= self.max_reconnects:
            try:
                self._consume_one_event()
                return
            except Exception as exc:
                last_exc = exc
                if attempts == self.max_reconnects:
                    break
                delay = self.backoff_seconds * (2**attempts)
                time.sleep(delay)
                attempts += 1
        raise FeedError(
            f"Eastmoney SSE failed after {self.max_reconnects + 1} attempts"
        ) from last_exc

    def _consume_one_event(self) -> None:
        url = self.sse_url or self._build_default_sse_url()
        response = self._get_request(
            url,
            headers={
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache",
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://quote.eastmoney.com/center/gridlist.html#hs_a_board",
            },
            stream=True,
            timeout=(self.connect_timeout, self.read_timeout),
        )
        try:
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
            iterator = response.iter_lines(decode_unicode=True)
            for raw_line in iterator:
                if raw_line is None:
                    continue
                line = (
                    raw_line.decode("utf-8")
                    if isinstance(raw_line, bytes)
                    else raw_line
                )
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                quote = self._quote_from_sse_payload(payload)
                if quote is None:
                    continue
                self._publish_quote(quote)
                return
            raise FeedError("Eastmoney SSE stream ended before quote payload")
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

    def _publish_quote(self, quote: dict[str, float]) -> None:
        price = float(quote["price"])
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

    def _build_default_sse_url(self) -> str:
        params = {
            "cb": "icomet_cb_0",
            "cname": self.cname,
            "seq": str(self.seq),
            "noop": str(self.noop),
            "token": self.token,
            "secid": self.secid,
            "_": str(int(time.time() * 1000)),
        }
        return "https://92.newspush.eastmoney.com/sse?" + urlencode(params)

    def _quote_from_sse_payload(self, payload: str) -> Optional[dict[str, float]]:
        try:
            event = json.loads(payload)
        except Exception:
            return self.parser(payload)

        if not isinstance(event, dict):
            return self.parser(payload)

        seq_value = event.get("seq")
        if isinstance(seq_value, int) and seq_value >= 0:
            self.seq = seq_value

        direct = self._quote_from_mapping(event)
        if direct is not None:
            return direct

        content = event.get("content")
        if isinstance(content, dict):
            nested = self._quote_from_mapping(content)
            if nested is not None:
                return nested
        elif isinstance(content, str) and content:
            try:
                parsed = json.loads(content)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                nested = self._quote_from_mapping(parsed)
                if nested is not None:
                    return nested

        if event.get("type") == "next_seq":
            return self._fetch_snapshot_quote()
        return self.parser(payload)

    def _fetch_snapshot_quote(self) -> Optional[dict[str, float]]:
        response = self._get_request(
            self.snapshot_url,
            params={
                "secid": self.secid,
                "fields": self.snapshot_fields,
                "ut": self.snapshot_ut,
            },
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://quote.eastmoney.com/center/gridlist.html#hs_a_board",
            },
            timeout=(self.connect_timeout, self.read_timeout),
        )
        try:
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
            payload = self._decode_snapshot_response(response)
            if not isinstance(payload, dict):
                return None
            data = payload.get("data")
            if isinstance(data, dict):
                quote = self._quote_from_mapping(data)
                if quote is not None:
                    return quote
            return self._quote_from_mapping(payload)
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

    def _decode_snapshot_response(self, response: Any) -> Any:
        if hasattr(response, "json"):
            try:
                return response.json()
            except Exception:
                pass

        text = getattr(response, "text", None)
        if not isinstance(text, str):
            return None

        raw = text.strip()
        if not raw:
            return None
        if raw.startswith("{"):
            return json.loads(raw)
        if raw.endswith(")") and "(" in raw:
            body = raw[raw.find("(") + 1 : -1]
            return json.loads(body)
        return None

    def _quote_from_mapping(
        self, source: Mapping[str, Any]
    ) -> Optional[dict[str, float]]:
        if "price" in source or "lastPrice" in source or "close" in source:
            price = _extract_float(source, ("price", "lastPrice", "close", "f2", "p"))
        else:
            price = _extract_float(
                source, ("f43", "f2", "p", "price", "lastPrice", "close")
            )
            if price is not None and "f43" in source and self.price_scale > 0:
                price = price / self.price_scale

        if price is None:
            return None

        volume = _extract_float(source, ("volume", "vol", "f47", "f5", "v")) or 0.0
        amount = _extract_float(source, ("amount", "turnover", "f48", "f6", "a")) or 0.0
        return {"price": price, "volume": volume, "amount": amount}

    @staticmethod
    def _default_cname(symbol: str) -> str:
        return hashlib.md5(f"eastmoney:{symbol}".encode("utf-8")).hexdigest()

    @staticmethod
    def _symbol_to_secid(symbol: str) -> str:
        code = symbol.strip()
        if not code:
            raise FeedError("symbol cannot be empty")
        market = "1" if code.startswith("6") else "0"
        return f"{market}.{code}"

    @staticmethod
    def _default_parser(data_line: str) -> Optional[dict[str, float]]:
        payload = json.loads(data_line)
        if not isinstance(payload, dict):
            return None

        source = payload
        content = payload.get("content")
        if isinstance(content, str) and content:
            try:
                parsed = json.loads(content)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                source = parsed
        elif isinstance(content, dict):
            source = content

        price = _extract_float(source, ("price", "lastPrice", "close", "f2", "p"))
        if price is None:
            return None
        volume = _extract_float(source, ("volume", "vol", "f5", "v")) or 0.0
        amount = _extract_float(source, ("amount", "turnover", "f6", "a")) or 0.0
        return {"price": price, "volume": volume, "amount": amount}


__all__ = ["RESTPollingFeed", "EastmoneySSEFeed"]
