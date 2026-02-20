from __future__ import annotations

from pybt.core.event_bus import EventBus
from pybt.core.events import MarketEvent
from pybt.data.rest_feed import EastmoneySSEFeed


class _FakeResponse:
    def __init__(self, lines: list[str], json_payload: dict | None = None) -> None:
        self._lines = lines
        self._json_payload = json_payload

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self, decode_unicode: bool = False):
        for line in self._lines:
            yield line if decode_unicode else line.encode("utf-8")

    def close(self) -> None:
        return None

    def json(self) -> dict:
        if self._json_payload is None:
            raise ValueError("json payload missing")
        return self._json_payload


def test_eastmoney_sse_feed_publishes_market_event() -> None:
    lines = [
        'data: {"type":"next_seq","seq":1,"content":""}',
        'data: {"content":{"price":12.34,"volume":1000,"amount":12340}}',
    ]

    def fake_get(*_args, **_kwargs):
        return _FakeResponse(lines)

    feed = EastmoneySSEFeed(
        symbol="000001",
        sse_url="https://example.com/sse",
        get_request=fake_get,
        max_ticks=1,
        backoff_seconds=0.0,
    )
    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    feed.next()
    bus.dispatch()

    assert len(captured) == 1
    assert captured[0].symbol == "000001"
    assert captured[0].fields["close"] == 12.34


def test_eastmoney_sse_feed_retries_connection() -> None:
    attempts = {"n": 0}

    def fake_get(*_args, **_kwargs):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("temporary")
        return _FakeResponse(['data: {"content":{"price":9.9}}'])

    feed = EastmoneySSEFeed(
        symbol="600000",
        sse_url="https://example.com/sse",
        get_request=fake_get,
        max_ticks=1,
        max_reconnects=3,
        backoff_seconds=0.0,
    )
    bus = EventBus()
    feed.bind(bus)
    bus.subscribe(MarketEvent, lambda _ev: None)

    feed.prime()
    feed.next()

    assert attempts["n"] == 3


def test_eastmoney_sse_feed_builds_default_url_for_symbol() -> None:
    called: dict[str, str] = {}

    def fake_get(url: str, **_kwargs):
        called["url"] = url
        return _FakeResponse(['data: {"content":{"price":8.8}}'])

    feed = EastmoneySSEFeed(
        symbol="600000",
        get_request=fake_get,
        max_ticks=1,
        backoff_seconds=0.0,
    )
    bus = EventBus()
    feed.bind(bus)
    bus.subscribe(MarketEvent, lambda _ev: None)

    feed.prime()
    feed.next()

    assert "92.newspush.eastmoney.com/sse" in called["url"]
    assert "secid=1.600000" in called["url"]


def test_eastmoney_sse_feed_uses_snapshot_on_next_seq_only() -> None:
    calls: list[str] = []

    def fake_get(url: str, **_kwargs):
        calls.append(url)
        if "newspush.eastmoney.com/sse" in url:
            return _FakeResponse(['data: {"type":"next_seq","seq":321,"content":""}'])
        return _FakeResponse(
            [],
            json_payload={
                "data": {
                    "f43": 989,
                    "f47": 700407,
                    "f48": 696614490.0,
                }
            },
        )

    feed = EastmoneySSEFeed(
        symbol="600000",
        get_request=fake_get,
        max_ticks=1,
        backoff_seconds=0.0,
        max_reconnects=0,
    )
    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    feed.next()
    bus.dispatch()

    assert len(captured) == 1
    assert captured[0].fields["close"] == 9.89
    assert any("push2.eastmoney.com/api/qt/stock/get" in url for url in calls)


def test_eastmoney_sse_feed_updates_seq_after_next_seq() -> None:
    calls: list[str] = []
    sse_round = {"n": 0}

    def fake_get(url: str, **_kwargs):
        calls.append(url)
        if "newspush.eastmoney.com/sse" in url:
            sse_round["n"] += 1
            if sse_round["n"] == 1:
                return _FakeResponse(
                    ['data: {"type":"next_seq","seq":777,"content":""}']
                )
            return _FakeResponse(['data: {"content":{"price":10.01}}'])
        return _FakeResponse([], json_payload={"data": {"f43": 1000}})

    feed = EastmoneySSEFeed(
        symbol="600000",
        get_request=fake_get,
        max_ticks=2,
        backoff_seconds=0.0,
        max_reconnects=0,
    )
    bus = EventBus()
    feed.bind(bus)
    bus.subscribe(MarketEvent, lambda _ev: None)

    feed.prime()
    feed.next()
    feed.next()

    sse_urls = [u for u in calls if "newspush.eastmoney.com/sse" in u]
    assert len(sse_urls) >= 2
    assert "seq=0" in sse_urls[0]
    assert "seq=777" in sse_urls[1]
