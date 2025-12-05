import asyncio
import json
from datetime import datetime

import pytest

from pybt.core.event_bus import EventBus
from pybt.core.events import MarketEvent
from pybt.data.websocket_feed import WebSocketJSONFeed


class _FakeWS:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.pings = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def recv(self) -> str:
        return json.dumps(self.payload)

    def ping(self) -> None:
        self.pings += 1


def test_websocket_feed_reconnects_with_backoff(monkeypatch):
    attempts = 0

    async def fake_connect(_url: str):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("connect fail")
        return _FakeWS({"price": 1.23})

    feed = WebSocketJSONFeed(
        symbol="AAA",
        url="ws://example.com",
        max_ticks=1,
        connect=fake_connect,
        max_reconnects=3,
        backoff_seconds=0.0,
        heartbeat_interval=1.0,
        loop=asyncio.new_event_loop(),
    )
    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    feed.next()
    bus.dispatch()

    assert attempts == 3
    assert captured and captured[0].fields["close"] == 1.23
    # heartbeat sent on successful connection
    assert feed._ticks == 1


def test_websocket_feed_raises_after_retries(monkeypatch):
    async def failing_connect(_url: str):
        raise RuntimeError("boom")

    feed = WebSocketJSONFeed(
        symbol="AAA",
        url="ws://example.com",
        max_ticks=1,
        connect=failing_connect,
        max_reconnects=1,
        backoff_seconds=0.0,
        loop=asyncio.new_event_loop(),
    )
    feed.bind(EventBus())
    feed.prime()
    with pytest.raises(Exception):
        feed.next()
