"""Generic WebSocket JSON feed (optional dependency).

Uses the `websockets` package to subscribe to a WebSocket endpoint that yields
JSON objects containing a `price` field and optional `volume`/`amount`.
This is a minimal adapter; production users should extend for authentication,
ping/pong and reconnection handling.
"""

import asyncio
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

try:
    import websockets  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    websockets = None

from pybt.core.interfaces import DataFeed
from pybt.core.models import Bar


class WebSocketJSONFeed(DataFeed):
    def __init__(
        self,
        symbol: str,
        url: str,
        parser: Optional[Callable[[Any], dict]] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        max_ticks: Optional[int] = None,
    ) -> None:
        super().__init__()
        if websockets is None:
            raise ImportError("websockets is required for WebSocketJSONFeed")
        self.symbol = symbol
        self.url = url
        self.parser = parser or self._default_parser
        self.loop = loop or asyncio.get_event_loop()
        self.max_ticks = max_ticks
        self._ticks = 0

    def prime(self) -> None:
        self._ticks = 0

    def has_next(self) -> bool:
        if self.max_ticks is None:
            return True
        return self._ticks < self.max_ticks

    def next(self) -> None:
        # Run one WebSocket message iteration synchronously for compatibility.
        self.loop.run_until_complete(self._next_async())

    async def _next_async(self) -> None:
        async with websockets.connect(self.url) as ws:  # type: ignore[attr-defined]
            raw = await ws.recv()
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

    @staticmethod
    def _default_parser(raw: Any) -> dict:
        import json

        payload = json.loads(raw)
        if "price" not in payload:
            raise RuntimeError("WebSocket payload missing 'price'")
        return payload


__all__ = ["WebSocketJSONFeed"]
