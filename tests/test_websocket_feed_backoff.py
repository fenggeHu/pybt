import asyncio
import json
from datetime import datetime

import pytest

from pybt.core.event_bus import EventBus
from pybt.core.events import MarketEvent
from pybt.data.websocket_feed import WebSocketJSONFeed
from pybt.errors import FeedError


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

    def ping(self) -> object:
        self.pings += 1
        return None


class _AwaitablePingWS(_FakeWS):
    def __init__(self, payload: dict) -> None:
        super().__init__(payload)
        self.ping_awaited = False

    def ping(self):
        self.pings += 1

        async def _ping() -> None:
            self.ping_awaited = True

        return _ping()


def test_websocket_feed_reconnects_with_backoff(monkeypatch):
    attempts = 0
    loop = asyncio.new_event_loop()

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
        loop=loop,
    )
    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    try:
        feed.prime()
        feed.next()
        bus.dispatch()
    finally:
        feed.on_stop()
        loop.close()

    assert attempts == 3
    assert captured and captured[0].fields["close"] == 1.23
    # heartbeat sent on successful connection
    assert feed._ticks == 1


def test_websocket_feed_raises_after_retries(monkeypatch):
    loop = asyncio.new_event_loop()

    async def failing_connect(_url: str):
        raise RuntimeError("boom")

    feed = WebSocketJSONFeed(
        symbol="AAA",
        url="ws://example.com",
        max_ticks=1,
        connect=failing_connect,
        max_reconnects=1,
        backoff_seconds=0.0,
        loop=loop,
    )
    feed.bind(EventBus())
    feed.prime()
    with pytest.raises(Exception):
        feed.next()
    feed.on_stop()
    loop.close()


def test_websocket_feed_creates_loop_when_missing():
    ws = _FakeWS({"price": 2.34})

    async def fake_connect(_url: str):
        return ws

    feed = WebSocketJSONFeed(
        symbol="AAA",
        url="ws://example.com",
        max_ticks=1,
        connect=fake_connect,
        backoff_seconds=0.0,
    )
    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    feed.next()
    bus.dispatch()
    feed.on_stop()

    assert captured and captured[0].fields["close"] == 2.34
    assert feed.loop.is_closed()


def test_websocket_feed_awaits_ping_coroutine():
    loop = asyncio.new_event_loop()
    ws = _AwaitablePingWS({"price": 9.87})

    async def fake_connect(_url: str):
        return ws

    feed = WebSocketJSONFeed(
        symbol="AAA",
        url="ws://example.com",
        max_ticks=1,
        connect=fake_connect,
        backoff_seconds=0.0,
        heartbeat_interval=1.0,
        loop=loop,
    )
    feed.bind(EventBus())

    try:
        feed.prime()
        feed.next()
    finally:
        feed.on_stop()
        loop.close()

    assert ws.pings == 1
    assert ws.ping_awaited is True


def test_websocket_feed_next_fails_inside_running_loop():
    async def _runner() -> None:
        async def fake_connect(_url: str):
            return _FakeWS({"price": 1.0})

        feed = WebSocketJSONFeed(
            symbol="AAA",
            url="ws://example.com",
            max_ticks=1,
            connect=fake_connect,
            backoff_seconds=0.0,
        )
        try:
            feed.prime()
            with pytest.raises(FeedError):
                feed.next()
        finally:
            feed.on_stop()

    asyncio.run(_runner())
