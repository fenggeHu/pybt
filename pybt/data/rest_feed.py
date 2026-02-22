"""Generic polling REST live feed.

Fetches price data from a REST endpoint or custom fetcher function and emits
MarketEvent slices. Designed for testing and extension; production users should
inject a hardened fetcher with retries and auth.
"""

import asyncio
import importlib
import inspect
import time
import hashlib
import json
import re
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Any, Callable, Mapping, Optional
from urllib.parse import urlencode

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    requests = None

try:
    import websockets  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    websockets = None

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
        request_timeout: float | tuple[float, float] = 5.0,
        session: Optional[Any] = None,
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
        self.request_timeout = request_timeout
        self._session = session
        self._owns_session = False
        if self._fetcher is None and self._session is None and requests is not None:
            self._session = requests.Session()
            self._owns_session = True
        self._sleep = time.sleep

    def prime(self) -> None:
        self._ticks = 0
        self._last_price = None

    def on_stop(self) -> None:
        if not self._owns_session or self._session is None:
            return
        close = getattr(self._session, "close", None)
        if callable(close):
            close()
        self._session = None

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
        if self._session is None:
            raise FeedError("requests session is required for RESTPollingFeed")
        resp = self._session.get(self.url, timeout=self.request_timeout)
        try:
            resp.raise_for_status()
            data = resp.json()
            if "price" not in data:
                raise FeedError("REST response missing 'price'")
            return data
        finally:
            close = getattr(resp, "close", None)
            if callable(close):
                close()

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
        sse_base_url: str = "https://92.newspush.eastmoney.com/sse",
        sse_headers: Optional[Mapping[str, str]] = None,
        snapshot_url: str = "https://push2.eastmoney.com/api/qt/stock/get",
        snapshot_fields: str = "f43,f47,f48",
        snapshot_ut: str = "fa5fd1943c7b386f172d6893dbfba10b",
        snapshot_headers: Optional[Mapping[str, str]] = None,
        snapshot_params: Optional[Mapping[str, Any]] = None,
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
        self.sse_base_url = sse_base_url
        self.sse_headers = self._merge_headers(
            {
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache",
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://quote.eastmoney.com/center/gridlist.html#hs_a_board",
            },
            sse_headers,
        )
        self.snapshot_url = snapshot_url
        self.snapshot_fields = snapshot_fields
        self.snapshot_ut = snapshot_ut
        self.snapshot_headers = self._merge_headers(
            {
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://quote.eastmoney.com/center/gridlist.html#hs_a_board",
            },
            snapshot_headers,
        )
        self.snapshot_params = dict(snapshot_params or {})
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
            headers=self.sse_headers,
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
        return self.sse_base_url.rstrip("?") + "?" + urlencode(params)

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
                **self.snapshot_params,
            },
            headers=self.snapshot_headers,
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
    def _merge_headers(
        base: Mapping[str, str], extra: Optional[Mapping[str, str]]
    ) -> dict[str, str]:
        out = dict(base)
        if extra:
            for k, v in extra.items():
                out[str(k)] = str(v)
        return out

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


def _symbol_to_secid(symbol: str) -> str:
    code = symbol.strip()
    if not code:
        raise FeedError("symbol cannot be empty")
    market = "1" if code.startswith("6") else "0"
    return f"{market}.{code}"


def _default_cname(symbol: str) -> str:
    return hashlib.md5(f"eastmoney:{symbol}".encode("utf-8")).hexdigest()


def _quote_from_mapping(
    source: Mapping[str, Any], *, price_scale: float
) -> Optional[dict[str, float]]:
    if "price" in source or "lastPrice" in source or "close" in source:
        price = _extract_float(source, ("price", "lastPrice", "close", "f2", "p"))
    else:
        price = _extract_float(
            source, ("f43", "f2", "p", "price", "lastPrice", "close")
        )
        if price is not None and "f43" in source and price_scale > 0:
            price = price / price_scale

    if price is None:
        return None

    volume = _extract_float(source, ("volume", "vol", "f47", "f5", "v")) or 0.0
    amount = _extract_float(source, ("amount", "turnover", "f48", "f6", "a")) or 0.0
    return {"price": price, "volume": volume, "amount": amount}


def _default_payload_parser(data_line: str) -> Optional[dict[str, float]]:
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


def _decode_snapshot_response(response: Any) -> Any:
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


def _build_default_sse_url(
    *,
    sse_base_url: str,
    cname: str,
    seq: int,
    noop: int,
    token: str,
    secid: str,
) -> str:
    params = {
        "cb": "icomet_cb_0",
        "cname": cname,
        "seq": str(seq),
        "noop": str(noop),
        "token": token,
        "secid": secid,
        "_": str(int(time.time() * 1000)),
    }
    return sse_base_url.rstrip("?") + "?" + urlencode(params)


def _ws_connect_headers_kwargs(
    connect: Any, headers: Mapping[str, str]
) -> dict[str, Any]:
    try:
        params = inspect.signature(connect).parameters
    except Exception:
        return {"extra_headers": dict(headers)}
    if "additional_headers" in params:
        return {"additional_headers": dict(headers)}
    if "extra_headers" in params:
        return {"extra_headers": dict(headers)}
    return {}


def _merge_headers_str(
    base: Mapping[str, str], extra: Optional[Mapping[str, str]]
) -> dict[str, str]:
    out = dict(base)
    if extra:
        for key, value in extra.items():
            out[str(key)] = str(value)
    return out


def _paths_from_value(value: Any) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for one in value:
            if isinstance(one, str) and one:
                out.append(one)
        return out
    return []


def _extract_by_path(source: Any, path: str) -> Any:
    current = source
    for part in path.split("."):
        token = part.strip()
        if not token:
            return None
        if isinstance(current, Mapping):
            if token not in current:
                return None
            current = current[token]
            continue
        if isinstance(current, (list, tuple)):
            try:
                idx = int(token)
            except Exception:
                return None
            if idx < 0 or idx >= len(current):
                return None
            current = current[idx]
            continue
        return None
    return current


def _extract_float_paths(source: Any, paths: list[str]) -> Optional[float]:
    for path in paths:
        value = _extract_by_path(source, path)
        if value is None:
            continue
        try:
            return float(value)
        except Exception:
            continue
    return None


def _quote_from_field_map(
    source: Any, field_map: Mapping[str, Any]
) -> Optional[dict[str, float]]:
    price_paths = _paths_from_value(field_map.get("price"))
    if not price_paths:
        return None
    price = _extract_float_paths(source, price_paths)
    if price is None:
        return None

    scale_value = field_map.get("price_scale")
    if scale_value is not None:
        try:
            scale = float(scale_value)
            if scale > 0:
                price = price / scale
        except Exception:
            pass

    volume = _extract_float_paths(source, _paths_from_value(field_map.get("volume")))
    amount = _extract_float_paths(source, _paths_from_value(field_map.get("amount")))
    return {
        "price": price,
        "volume": volume if volume is not None else 0.0,
        "amount": amount if amount is not None else 0.0,
    }


class EastmoneyQuotePlugin(ABC):
    @abstractmethod
    def next_quote(
        self, feed: "EastmoneySSEExtendedFeed"
    ) -> Optional[dict[str, float]]:
        """Return one quote or None when this plugin has no output right now."""

    def close(self) -> None:
        return


class EastmoneySSESourcePlugin(EastmoneyQuotePlugin):
    def __init__(
        self,
        *,
        get_request: Callable[..., Any],
        parser: Callable[[str], Optional[dict[str, float]]],
        sse_url: Optional[str],
        sse_base_url: str,
        headers: Mapping[str, str],
        connect_timeout: float,
        read_timeout: float,
        reconnect_every_ticks: Optional[int],
        heartbeat_timeout: Optional[float],
        field_map: Optional[Mapping[str, Any]] = None,
        token: Optional[str] = None,
        cname: Optional[str] = None,
        noop: Optional[int] = None,
    ) -> None:
        self._get_request = get_request
        self._parser = parser
        self._sse_url = sse_url
        self._sse_base_url = sse_base_url
        self._headers = dict(headers)
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._reconnect_every_ticks = reconnect_every_ticks
        self._heartbeat_timeout = heartbeat_timeout
        self._field_map = dict(field_map) if field_map is not None else None
        self._token = token
        self._cname = cname
        self._noop = noop
        self._stream_response: Any = None
        self._stream_iter: Any = None
        self._ticks_since_connect = 0
        self._last_stream_activity = 0.0
        self._now = time.monotonic

    def next_quote(
        self, feed: "EastmoneySSEExtendedFeed"
    ) -> Optional[dict[str, float]]:
        if (
            isinstance(self._reconnect_every_ticks, int)
            and self._reconnect_every_ticks > 0
            and self._ticks_since_connect >= self._reconnect_every_ticks
        ):
            self.close()

        if self._stream_iter is None:
            self._open_stream(feed)

        while True:
            self._check_heartbeat()
            assert self._stream_iter is not None
            try:
                raw_line = next(self._stream_iter)
            except StopIteration as exc:
                self.close()
                if feed.snapshot_requested:
                    return None
                raise FeedError(
                    "Eastmoney SSE stream ended before quote payload"
                ) from exc

            self._last_stream_activity = self._now()
            if raw_line is None:
                continue
            line = (
                raw_line.decode("utf-8")
                if isinstance(raw_line, (bytes, bytearray))
                else raw_line
            )
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            quote = self._quote_from_payload(feed, payload)
            if quote is None:
                if feed.snapshot_requested:
                    # Let snapshot_api/api fallback sources run immediately.
                    return None
                continue
            self._ticks_since_connect += 1
            return quote

    def close(self) -> None:
        response = self._stream_response
        self._stream_response = None
        self._stream_iter = None
        self._ticks_since_connect = 0
        self._last_stream_activity = 0.0
        if response is None:
            return
        close = getattr(response, "close", None)
        if callable(close):
            close()

    def _open_stream(self, feed: "EastmoneySSEExtendedFeed") -> None:
        url = self._sse_url
        if not url:
            url = _build_default_sse_url(
                sse_base_url=self._sse_base_url,
                cname=self._cname or feed.cname,
                seq=feed.seq,
                noop=self._noop if self._noop is not None else feed.noop,
                token=self._token if self._token is not None else feed.token,
                secid=feed.secid,
            )
        response = self._get_request(
            url,
            headers=self._headers,
            stream=True,
            timeout=(self._connect_timeout, self._read_timeout),
        )
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        self._stream_response = response
        self._stream_iter = response.iter_lines(decode_unicode=True)
        self._ticks_since_connect = 0
        self._last_stream_activity = self._now()

    def _check_heartbeat(self) -> None:
        timeout = self._heartbeat_timeout
        if timeout is None or timeout <= 0 or self._last_stream_activity <= 0:
            return
        idle = self._now() - self._last_stream_activity
        if idle <= timeout:
            return
        self.close()
        raise FeedError(
            f"Eastmoney SSE heartbeat timeout: idle={idle:.3f}s > {timeout:.3f}s"
        )

    def _quote_from_payload(
        self, feed: "EastmoneySSEExtendedFeed", payload: str
    ) -> Optional[dict[str, float]]:
        try:
            event = json.loads(payload)
        except Exception:
            return self._parser(payload)

        if not isinstance(event, dict):
            return self._parser(payload)

        seq_value = event.get("seq")
        if isinstance(seq_value, int) and seq_value >= 0:
            feed.seq = seq_value

        direct = self._quote_from_mapping_or_field_map(event, feed=feed)
        if direct is not None:
            return direct

        content = event.get("content")
        if isinstance(content, dict):
            nested = self._quote_from_mapping_or_field_map(content, feed=feed)
            if nested is not None:
                return nested
        elif isinstance(content, str) and content:
            try:
                parsed = json.loads(content)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                nested = self._quote_from_mapping_or_field_map(parsed, feed=feed)
                if nested is not None:
                    return nested

        if event.get("type") == "next_seq":
            feed.request_snapshot()
            return None

        return self._parser(payload)

    def _quote_from_mapping_or_field_map(
        self, source: Mapping[str, Any], *, feed: "EastmoneySSEExtendedFeed"
    ) -> Optional[dict[str, float]]:
        if self._field_map is not None:
            mapped = _quote_from_field_map(source, self._field_map)
            if mapped is not None:
                return mapped
        return _quote_from_mapping(source, price_scale=feed.price_scale)


class EastmoneySnapshotAPIPlugin(EastmoneyQuotePlugin):
    def __init__(
        self,
        *,
        get_request: Callable[..., Any],
        snapshot_url: str,
        snapshot_fields: str,
        snapshot_ut: str,
        headers: Mapping[str, str],
        params: Mapping[str, Any],
        connect_timeout: float,
        read_timeout: float,
        on_demand_only: bool = True,
        field_map: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self._get_request = get_request
        self._snapshot_url = snapshot_url
        self._snapshot_fields = snapshot_fields
        self._snapshot_ut = snapshot_ut
        self._headers = dict(headers)
        self._params = dict(params)
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._on_demand_only = on_demand_only
        self._field_map = dict(field_map) if field_map is not None else None

    def next_quote(
        self, feed: "EastmoneySSEExtendedFeed"
    ) -> Optional[dict[str, float]]:
        if self._on_demand_only and (not feed.snapshot_requested):
            return None
        response = self._get_request(
            self._snapshot_url,
            params={
                "secid": feed.secid,
                "fields": self._snapshot_fields,
                "ut": self._snapshot_ut,
                **self._params,
            },
            headers=self._headers,
            timeout=(self._connect_timeout, self._read_timeout),
        )
        try:
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
            payload = _decode_snapshot_response(response)
            if not isinstance(payload, dict):
                return None
            mapped_payload = self._quote_from_mapping_or_field_map(payload, feed=feed)
            if mapped_payload is not None:
                feed.clear_snapshot_request()
                return mapped_payload
            data = payload.get("data")
            if isinstance(data, dict):
                quote = self._quote_from_mapping_or_field_map(data, feed=feed)
                if quote is not None:
                    feed.clear_snapshot_request()
                    return quote
            return None
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

    def _quote_from_mapping_or_field_map(
        self, source: Mapping[str, Any], *, feed: "EastmoneySSEExtendedFeed"
    ) -> Optional[dict[str, float]]:
        if self._field_map is not None:
            mapped = _quote_from_field_map(source, self._field_map)
            if mapped is not None:
                return mapped
        return _quote_from_mapping(source, price_scale=feed.price_scale)


def _response_text(
    response: Any, *, encoding: Optional[str] = None, errors: str = "ignore"
) -> Optional[str]:
    content = getattr(response, "content", None)
    if isinstance(content, (bytes, bytearray)):
        if encoding:
            return bytes(content).decode(encoding, errors=errors)
        try:
            return bytes(content).decode("utf-8")
        except Exception:
            return bytes(content).decode("utf-8", errors=errors)
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    return None


def _decode_json_response(response: Any) -> Any:
    if hasattr(response, "json"):
        try:
            return response.json()
        except Exception:
            pass
    text = _response_text(response)
    if not isinstance(text, str):
        return None
    raw = text.strip()
    if not raw:
        return None
    if raw.startswith("{") or raw.startswith("["):
        return json.loads(raw)
    return None


def _decode_sina_hq_payload(response: Any, *, encoding: str = "gbk") -> Any:
    text = _response_text(response, encoding=encoding)
    if not isinstance(text, str):
        return None
    match = re.search(r'var\s+hq_str_[^=]+="([^"]*)"', text)
    if not match:
        return None
    return match.group(1).split(",")


class APIQuoteSourcePlugin(EastmoneyQuotePlugin):
    def __init__(
        self,
        *,
        get_request: Callable[..., Any],
        url: str,
        headers: Mapping[str, str],
        params: Mapping[str, Any],
        connect_timeout: float,
        read_timeout: float,
        on_demand_only: bool = False,
        field_map: Optional[Mapping[str, Any]] = None,
        response_mode: str = "json_or_jsonp",
        symbol_param: Optional[str] = None,
        symbol_template: str = "{symbol}",
        symbol_transform: Optional[str] = None,
        encoding: Optional[str] = None,
    ) -> None:
        self._get_request = get_request
        self._url = url
        self._headers = dict(headers)
        self._params = dict(params)
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._on_demand_only = on_demand_only
        self._field_map = dict(field_map) if field_map is not None else None
        self._response_mode = response_mode.strip().lower()
        self._symbol_param = symbol_param.strip() if symbol_param else None
        self._symbol_template = symbol_template
        self._symbol_transform = (
            symbol_transform.strip().lower() if symbol_transform else None
        )
        self._encoding = encoding

    def next_quote(
        self, feed: "EastmoneySSEExtendedFeed"
    ) -> Optional[dict[str, float]]:
        if self._on_demand_only and (not feed.snapshot_requested):
            return None
        symbol = self._transform_symbol(feed.symbol)
        url = self._url.format(symbol=symbol) if "{symbol}" in self._url else self._url
        params = dict(self._params)
        if self._symbol_param:
            params[self._symbol_param] = self._symbol_template.format(symbol=symbol)
        response = self._get_request(
            url,
            params=params,
            headers=self._headers,
            timeout=(self._connect_timeout, self._read_timeout),
        )
        try:
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
            payload = self._decode_payload(response)
            quote = self._quote_from_payload(payload, feed=feed)
            if quote is None:
                return None
            if self._on_demand_only:
                feed.clear_snapshot_request()
            return quote
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

    def _decode_payload(self, response: Any) -> Any:
        mode = self._response_mode
        if mode in {"json", "application/json"}:
            return _decode_json_response(response)
        if mode in {"json_or_jsonp", "jsonp"}:
            return _decode_snapshot_response(response)
        if mode in {"sina_hq", "sina"}:
            return _decode_sina_hq_payload(response, encoding=self._encoding or "gbk")
        if mode == "text":
            return _response_text(response, encoding=self._encoding)
        raise ValueError(f"Unsupported api response_mode: {self._response_mode}")

    def _quote_from_payload(
        self, payload: Any, *, feed: "EastmoneySSEExtendedFeed"
    ) -> Optional[dict[str, float]]:
        if self._field_map is not None:
            mapped = _quote_from_field_map(payload, self._field_map)
            if mapped is not None:
                return mapped
        if isinstance(payload, Mapping):
            quote = _quote_from_mapping(payload, price_scale=feed.price_scale)
            if quote is not None:
                return quote
            data = payload.get("data")
            if isinstance(data, Mapping):
                return _quote_from_mapping(data, price_scale=feed.price_scale)
        return None

    def _transform_symbol(self, symbol: str) -> str:
        mode = self._symbol_transform
        if mode in {None, "", "none", "raw"}:
            return symbol
        if mode == "secid":
            return _symbol_to_secid(symbol)
        if mode in {"cn_prefix", "shsz"}:
            code = symbol.strip()
            if code.startswith(("sh", "sz")):
                return code
            market = "sh" if code.startswith(("5", "6", "9")) else "sz"
            return f"{market}{code}"
        raise ValueError(f"Unsupported symbol_transform: {mode}")


class EastmoneyWebSocketSourcePlugin(EastmoneyQuotePlugin):
    def __init__(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        parser: Callable[[str], Optional[dict[str, float]]],
        heartbeat_interval: Optional[float] = None,
        field_map: Optional[Mapping[str, Any]] = None,
        connect: Optional[Callable[..., Any]] = None,
    ) -> None:
        if websockets is None and connect is None:
            raise FeedError("websockets is required for websocket plugin")
        self._url = url
        self._headers = dict(headers)
        self._parser = parser
        self._heartbeat_interval = heartbeat_interval
        self._field_map = dict(field_map) if field_map is not None else None
        self._connect = connect or websockets.connect  # type: ignore[attr-defined]
        self._loop = asyncio.new_event_loop()
        self._owns_loop = True
        self._ws: Any = None
        self._ws_context: Any = None

    def next_quote(
        self, feed: "EastmoneySSEExtendedFeed"
    ) -> Optional[dict[str, float]]:
        if self._loop.is_running():
            raise FeedError("websocket plugin loop is already running")
        return self._loop.run_until_complete(self._next_quote_async(feed))

    def close(self) -> None:
        if self._ws is not None:
            self._loop.run_until_complete(self._close_ws_async())

    def __del__(self) -> None:
        if self._owns_loop and (not self._loop.is_closed()):
            self._loop.close()

    async def _next_quote_async(
        self, feed: "EastmoneySSEExtendedFeed"
    ) -> Optional[dict[str, float]]:
        ws = await self._ensure_ws()
        if self._heartbeat_interval is not None and hasattr(ws, "ping"):
            try:
                ping = ws.ping()
                if inspect.isawaitable(ping):
                    await ping
            except Exception:
                pass
        raw = await ws.recv()
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        if isinstance(raw, str):
            payload = self._parser(raw)
            if payload is not None:
                return payload
            try:
                event = json.loads(raw)
            except Exception:
                return None
            if isinstance(event, dict):
                direct = self._quote_from_mapping_or_field_map(event, feed=feed)
                if direct is not None:
                    return direct
                content = event.get("content")
                if isinstance(content, dict):
                    return self._quote_from_mapping_or_field_map(content, feed=feed)
        return None

    async def _ensure_ws(self) -> Any:
        if self._ws is not None:
            return self._ws
        kwargs = _ws_connect_headers_kwargs(self._connect, self._headers)
        ws_ctx = self._connect(self._url, **kwargs)
        if inspect.isawaitable(ws_ctx):
            ws_ctx = await ws_ctx
        if hasattr(ws_ctx, "__aenter__"):
            self._ws_context = ws_ctx
            self._ws = await ws_ctx.__aenter__()
            return self._ws
        self._ws = ws_ctx
        return self._ws

    async def _close_ws_async(self) -> None:
        ws = self._ws
        ws_ctx = self._ws_context
        self._ws = None
        self._ws_context = None
        if ws_ctx is not None and hasattr(ws_ctx, "__aexit__"):
            await ws_ctx.__aexit__(None, None, None)
            return
        if ws is None:
            return
        close = getattr(ws, "close", None)
        if callable(close):
            result = close()
            if inspect.isawaitable(result):
                await result

    def _quote_from_mapping_or_field_map(
        self, source: Mapping[str, Any], *, feed: "EastmoneySSEExtendedFeed"
    ) -> Optional[dict[str, float]]:
        if self._field_map is not None:
            mapped = _quote_from_field_map(source, self._field_map)
            if mapped is not None:
                return mapped
        return _quote_from_mapping(source, price_scale=feed.price_scale)


class EastmoneySSEExtendedFeed(DataFeed):
    """Pluggable real-time quote feed.

    Source transport is fully config-driven. You can configure one or more
    plugins (`sse`, `snapshot_api`, `websocket`, custom plugin) and switch
    behavior without changing Python code.
    """

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
        sse_base_url: str = "https://92.newspush.eastmoney.com/sse",
        sse_headers: Optional[Mapping[str, str]] = None,
        snapshot_url: str = "https://push2.eastmoney.com/api/qt/stock/get",
        snapshot_fields: str = "f43,f47,f48",
        snapshot_ut: str = "fa5fd1943c7b386f172d6893dbfba10b",
        snapshot_headers: Optional[Mapping[str, str]] = None,
        snapshot_params: Optional[Mapping[str, Any]] = None,
        price_scale: float = 100.0,
        reconnect_every_ticks: Optional[int] = None,
        heartbeat_timeout: Optional[float] = None,
        sources: Optional[list[Mapping[str, Any]]] = None,
    ) -> None:
        super().__init__()
        self.symbol = symbol
        self.secid = secid or _symbol_to_secid(symbol)
        self.token = token
        self.cname = cname or _default_cname(symbol)
        self.seq = seq
        self.noop = noop
        self.max_ticks = max_ticks
        self.max_reconnects = max_reconnects
        self.backoff_seconds = backoff_seconds
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.price_scale = price_scale
        self.sse_url = sse_url
        self._ticks = 0
        self._last_price: Optional[float] = None
        self._snapshot_requested = False

        request_fn = get_request or (requests.get if requests is not None else None)
        parser_fn = parser or _default_payload_parser

        sse_headers_final = _merge_headers_str(
            {
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache",
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://quote.eastmoney.com/center/gridlist.html#hs_a_board",
            },
            sse_headers,
        )
        snapshot_headers_final = _merge_headers_str(
            {
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://quote.eastmoney.com/center/gridlist.html#hs_a_board",
            },
            snapshot_headers,
        )

        specs = list(sources or [])
        if not specs:
            specs = [
                {
                    "type": "sse",
                    "sse_url": sse_url,
                    "sse_base_url": sse_base_url,
                    "headers": sse_headers_final,
                    "reconnect_every_ticks": reconnect_every_ticks,
                    "heartbeat_timeout": heartbeat_timeout,
                    "token": token,
                    "cname": self.cname,
                    "noop": noop,
                },
                {
                    "type": "snapshot_api",
                    "snapshot_url": snapshot_url,
                    "snapshot_fields": snapshot_fields,
                    "snapshot_ut": snapshot_ut,
                    "headers": snapshot_headers_final,
                    "params": dict(snapshot_params or {}),
                    "on_demand_only": True,
                },
            ]
        self._plugins = self._build_plugins(
            specs=specs,
            get_request=request_fn,
            parser=parser_fn,
            default_sse_base_url=sse_base_url,
            default_sse_headers=sse_headers_final,
            default_snapshot_url=snapshot_url,
            default_snapshot_fields=snapshot_fields,
            default_snapshot_ut=snapshot_ut,
            default_snapshot_headers=snapshot_headers_final,
            default_snapshot_params=dict(snapshot_params or {}),
        )
        if not self._plugins:
            raise FeedError("Feed has no enabled source plugins")

    @property
    def snapshot_requested(self) -> bool:
        return self._snapshot_requested

    def request_snapshot(self) -> None:
        self._snapshot_requested = True

    def clear_snapshot_request(self) -> None:
        self._snapshot_requested = False

    def prime(self) -> None:
        self._ticks = 0
        self._last_price = None
        self._snapshot_requested = False
        self._close_plugins()

    def on_stop(self) -> None:
        self._close_plugins()

    def has_next(self) -> bool:
        if self.max_ticks is None:
            return True
        return self._ticks < self.max_ticks

    def next(self) -> None:
        attempts = 0
        last_exc: Optional[Exception] = None
        while attempts <= self.max_reconnects:
            try:
                for plugin in self._plugins:
                    quote = plugin.next_quote(self)
                    if quote is None:
                        continue
                    self._publish_quote(quote)
                    return
                raise FeedError("No source plugin produced quote")
            except Exception as exc:
                last_exc = exc
                if attempts == self.max_reconnects:
                    break
                self._close_plugins()
                delay = self.backoff_seconds * (2**attempts)
                time.sleep(delay)
                attempts += 1
        raise FeedError(
            f"Source plugin feed failed after {self.max_reconnects + 1} attempts"
        ) from last_exc

    def _publish_quote(self, quote: Mapping[str, Any]) -> None:
        price = float(quote["price"])
        ts = datetime.utcnow()
        last = self._last_price or price
        bar = Bar(
            symbol=self.symbol,
            timestamp=ts,
            open=last,
            high=max(last, price),
            low=min(last, price),
            close=price,
            volume=float(quote.get("volume", 0.0)),
            amount=float(quote.get("amount", 0.0)),
        )
        self._last_price = price
        self._ticks += 1
        self.bus.publish(bar.as_event())

    def _close_plugins(self) -> None:
        for plugin in self._plugins:
            try:
                plugin.close()
            except Exception:
                continue

    def _build_plugins(
        self,
        *,
        specs: list[Mapping[str, Any]],
        get_request: Optional[Callable[..., Any]],
        parser: Callable[[str], Optional[dict[str, float]]],
        default_sse_base_url: str,
        default_sse_headers: Mapping[str, str],
        default_snapshot_url: str,
        default_snapshot_fields: str,
        default_snapshot_ut: str,
        default_snapshot_headers: Mapping[str, str],
        default_snapshot_params: Mapping[str, Any],
    ) -> list[EastmoneyQuotePlugin]:
        plugins: list[EastmoneyQuotePlugin] = []
        for idx, spec in enumerate(specs):
            if not isinstance(spec, Mapping):
                raise ValueError(f"sources[{idx}] must be an object")
            if not self._is_enabled(spec.get("enabled", True)):
                continue
            source_type = str(spec.get("type", "")).strip().lower()
            if source_type == "sse":
                if get_request is None:
                    raise FeedError(
                        "sse source requires requests or custom get_request"
                    )
                field_map = self._as_optional_object(
                    spec.get("field_map"), "sse.field_map"
                )
                plugins.append(
                    EastmoneySSESourcePlugin(
                        get_request=get_request,
                        parser=parser,
                        sse_url=self._as_optional_str(spec.get("sse_url")),
                        sse_base_url=str(
                            spec.get("sse_base_url", default_sse_base_url)
                        ),
                        headers=self._merge_headers(
                            default_sse_headers, spec.get("headers")
                        ),
                        connect_timeout=float(
                            spec.get("connect_timeout", self.connect_timeout)
                        ),
                        read_timeout=float(spec.get("read_timeout", self.read_timeout)),
                        reconnect_every_ticks=self._as_optional_int(
                            spec.get("reconnect_every_ticks")
                        ),
                        heartbeat_timeout=self._as_optional_float(
                            spec.get("heartbeat_timeout")
                        ),
                        field_map=field_map,
                        token=self._as_optional_str(spec.get("token")),
                        cname=self._as_optional_str(spec.get("cname")),
                        noop=self._as_optional_int(spec.get("noop")),
                    )
                )
                continue
            if source_type in {"api", "snapshot_api", "snapshot"}:
                if source_type == "api":
                    if get_request is None:
                        raise FeedError(
                            "api source requires requests or custom get_request"
                        )
                    field_map = self._as_optional_object(
                        spec.get("field_map"), "api.field_map"
                    )
                    url = spec.get("url", spec.get("snapshot_url"))
                    if not isinstance(url, str) or not url:
                        raise ValueError("api source requires 'url'")
                    plugins.append(
                        APIQuoteSourcePlugin(
                            get_request=get_request,
                            url=url,
                            headers=self._merge_headers({}, spec.get("headers")),
                            params=self._merge_mapping({}, spec.get("params")),
                            connect_timeout=float(
                                spec.get("connect_timeout", self.connect_timeout)
                            ),
                            read_timeout=float(
                                spec.get("read_timeout", self.read_timeout)
                            ),
                            on_demand_only=bool(spec.get("on_demand_only", False)),
                            field_map=field_map,
                            response_mode=str(
                                spec.get("response_mode", "json_or_jsonp")
                            ),
                            symbol_param=self._as_optional_str(
                                spec.get("symbol_param")
                            ),
                            symbol_template=str(
                                spec.get("symbol_template", "{symbol}")
                            ),
                            symbol_transform=self._as_optional_str(
                                spec.get("symbol_transform")
                            ),
                            encoding=self._as_optional_str(spec.get("encoding")),
                        )
                    )
                    continue
                if get_request is None:
                    raise FeedError(
                        "snapshot_api source requires requests or custom get_request"
                    )
                field_map = self._as_optional_object(
                    spec.get("field_map"), "snapshot_api.field_map"
                )
                plugins.append(
                    EastmoneySnapshotAPIPlugin(
                        get_request=get_request,
                        snapshot_url=str(
                            spec.get("snapshot_url", default_snapshot_url)
                        ),
                        snapshot_fields=str(
                            spec.get("snapshot_fields", default_snapshot_fields)
                        ),
                        snapshot_ut=str(spec.get("snapshot_ut", default_snapshot_ut)),
                        headers=self._merge_headers(
                            default_snapshot_headers, spec.get("headers")
                        ),
                        params=self._merge_mapping(
                            default_snapshot_params, spec.get("params")
                        ),
                        connect_timeout=float(
                            spec.get("connect_timeout", self.connect_timeout)
                        ),
                        read_timeout=float(spec.get("read_timeout", self.read_timeout)),
                        on_demand_only=bool(spec.get("on_demand_only", True)),
                        field_map=field_map,
                    )
                )
                continue
            if source_type == "websocket":
                ws_url = spec.get("url")
                if not isinstance(ws_url, str) or not ws_url:
                    raise ValueError("websocket source requires 'url'")
                field_map = self._as_optional_object(
                    spec.get("field_map"), "websocket.field_map"
                )
                plugins.append(
                    EastmoneyWebSocketSourcePlugin(
                        url=ws_url,
                        headers=self._merge_headers({}, spec.get("headers")),
                        parser=parser,
                        heartbeat_interval=self._as_optional_float(
                            spec.get("heartbeat_interval")
                        ),
                        field_map=field_map,
                    )
                )
                continue
            if source_type == "plugin":
                class_path = spec.get("class_path")
                if not isinstance(class_path, str) or "." not in class_path:
                    raise ValueError(
                        "plugin source requires class_path in '<module>.<Class>' format"
                    )
                params = spec.get("params", {})
                if not isinstance(params, Mapping):
                    raise ValueError("plugin source params must be an object")
                module_name, _, class_name = class_path.rpartition(".")
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name)
                plugin = cls(**dict(params))
                if not hasattr(plugin, "next_quote"):
                    raise ValueError(
                        f"plugin '{class_path}' must implement next_quote(feed)"
                    )
                plugins.append(plugin)  # type: ignore[arg-type]
                continue
            raise ValueError(f"Unsupported source type: {source_type}")
        return plugins

    @staticmethod
    def _as_optional_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        return int(value)

    @staticmethod
    def _as_optional_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _as_optional_str(value: Any) -> Optional[str]:
        if value is None:
            return None
        out = str(value)
        return out if out else None

    @staticmethod
    def _as_optional_object(value: Any, field_name: str) -> Optional[dict[str, Any]]:
        if value is None:
            return None
        if not isinstance(value, Mapping):
            raise ValueError(f"{field_name} must be an object")
        out: dict[str, Any] = {}
        for key, one in value.items():
            out[str(key)] = one
        return out

    @staticmethod
    def _merge_headers(base: Mapping[str, str], extra: Any) -> dict[str, str]:
        out = dict(base)
        if extra is None:
            return out
        if not isinstance(extra, Mapping):
            raise ValueError("plugin headers must be an object")
        for key, value in extra.items():
            out[str(key)] = str(value)
        return out

    @staticmethod
    def _merge_mapping(base: Mapping[str, Any], extra: Any) -> dict[str, Any]:
        out = dict(base)
        if extra is None:
            return out
        if not isinstance(extra, Mapping):
            raise ValueError("plugin params must be an object")
        for key, value in extra.items():
            out[str(key)] = value
        return out

    @staticmethod
    def _is_enabled(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() not in {"0", "false", "off", "no"}
        return bool(value)


class QuoteSourcePlugin(EastmoneyQuotePlugin):
    """Provider-agnostic alias of EastmoneyQuotePlugin."""


class SSEQuoteSourcePlugin(EastmoneySSESourcePlugin):
    """Provider-agnostic alias of EastmoneySSESourcePlugin."""


class SnapshotAPIQuoteSourcePlugin(EastmoneySnapshotAPIPlugin):
    """Provider-agnostic alias of EastmoneySnapshotAPIPlugin."""


class WebSocketQuoteSourcePlugin(EastmoneyWebSocketSourcePlugin):
    """Provider-agnostic alias of EastmoneyWebSocketSourcePlugin."""


class ComposableQuoteFeed(EastmoneySSEExtendedFeed):
    """Provider-agnostic alias of EastmoneySSEExtendedFeed."""


__all__ = [
    "RESTPollingFeed",
    "EastmoneySSEFeed",
    "EastmoneySSEExtendedFeed",
    "QuoteSourcePlugin",
    "SSEQuoteSourcePlugin",
    "SnapshotAPIQuoteSourcePlugin",
    "WebSocketQuoteSourcePlugin",
    "ComposableQuoteFeed",
]
