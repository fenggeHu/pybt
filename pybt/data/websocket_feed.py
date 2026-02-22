"""Generic WebSocket JSON feed (optional dependency).

Uses the `websockets` package to subscribe to a WebSocket endpoint that yields
JSON objects containing a `price` field and optional `volume`/`amount`.
This is a minimal adapter; production users should extend for authentication,
ping/pong and reconnection handling.
"""

import asyncio
import inspect
import json
from datetime import datetime
from typing import Any, Callable, Optional

try:
    import websockets  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    websockets = None

from pybt.core.interfaces import DataFeed
from pybt.core.models import Bar
from pybt.errors import FeedError


class WebSocketJSONFeed(DataFeed):
    def __init__(
        self,
        symbol: str,
        url: str,
        parser: Optional[Callable[[Any], dict]] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        max_ticks: Optional[int] = None,
        connect: Optional[Callable[[str], Any]] = None,
        max_reconnects: int = 3,
        backoff_seconds: float = 0.5,
        heartbeat_interval: Optional[float] = None,
    ) -> None:
        super().__init__()
        if websockets is None and connect is None:
            raise FeedError("websockets is required for WebSocketJSONFeed")
        self.symbol = symbol
        self.url = url
        self.parser = parser or self._default_parser
        self.loop, self._owns_loop = self._resolve_loop(loop)
        self.max_ticks = max_ticks
        self._ticks = 0
        self.backoff_seconds = backoff_seconds
        self.max_reconnects = max_reconnects
        self._connect = connect or websockets.connect  # type: ignore[attr-defined]
        self.heartbeat_interval = heartbeat_interval
        self._ws: Any = None
        self._ws_context: Any = None

    @staticmethod
    def _resolve_loop(
        loop: Optional[asyncio.AbstractEventLoop],
    ) -> tuple[asyncio.AbstractEventLoop, bool]:
        if loop is not None:
            return loop, False
        return asyncio.new_event_loop(), True

    def prime(self) -> None:
        self._ticks = 0
        self._close_ws_sync()

    def on_stop(self) -> None:
        self._close_ws_sync()
        if self._owns_loop and not self.loop.is_closed():
            self.loop.close()

    def has_next(self) -> bool:
        if self.max_ticks is None:
            return True
        return self._ticks < self.max_ticks

    def next(self) -> None:
        # Run one WebSocket message iteration synchronously for compatibility.
        if self.loop.is_running():
            raise FeedError(
                "WebSocketJSONFeed.next() cannot be called with a running event loop. "
                "Run the feed in a dedicated thread/process, or use an async integration."
            )
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise FeedError(
                "WebSocketJSONFeed.next() cannot be called from within a running asyncio loop. "
                "Run the feed in a dedicated thread/process, or use an async integration."
            )
        self.loop.run_until_complete(self._next_async())

    async def _next_async(self) -> None:
        # WebSocket transport supplies raw payloads; this feed owns reconnect/backoff before publishing MarketEvent bars.
        attempts = 0
        while attempts <= self.max_reconnects:
            try:
                ws = await self._ensure_ws()
                raw = await self._recv_with_heartbeat(ws)

                payload = self.parser(raw)
                price = payload["price"]
                ts = datetime.utcnow()
                bar = Bar(
                    symbol=self.symbol,
                    timestamp=ts,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=float(payload.get("volume", 0.0)),
                    amount=float(payload.get("amount", 0.0)),
                )
                self.bus.publish(bar.as_event())
                self._ticks += 1
                return
            except Exception as exc:
                attempts += 1
                await self._close_ws_async()
                if attempts > self.max_reconnects:
                    raise FeedError(
                        f"WebSocket connection failed after {self.max_reconnects} attempts"
                    ) from exc
                delay = self.backoff_seconds * (2 ** (attempts - 1))
                await asyncio.sleep(delay)

    @staticmethod
    def _default_parser(raw: Any) -> dict:
        payload = json.loads(raw)
        if "price" not in payload:
            raise FeedError("WebSocket payload missing 'price'")
        return payload

    async def _recv_with_heartbeat(self, ws: Any) -> Any:
        if self.heartbeat_interval is not None and hasattr(ws, "ping"):
            try:
                result = ws.ping()
                if inspect.isawaitable(result):
                    await result
            except Exception:
                pass
        return await ws.recv()

    async def _ensure_ws(self) -> Any:
        if self._ws is not None:
            return self._ws
        ws_ctx = self._connect(self.url)
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

    def _close_ws_sync(self) -> None:
        if self.loop.is_closed() or self.loop.is_running():
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            return
        self.loop.run_until_complete(self._close_ws_async())


__all__ = ["WebSocketJSONFeed"]
