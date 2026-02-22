from __future__ import annotations

from pybt.core.event_bus import EventBus
from pybt.core.events import MarketEvent
from pybt.data.rest_feed import ComposableQuoteFeed, EastmoneySSEExtendedFeed


class _FakeResponse:
    def __init__(self, lines: list[str], json_payload: dict | None = None) -> None:
        self._lines = lines
        self._json_payload = json_payload
        self.closed = False

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self, decode_unicode: bool = False):
        for line in self._lines:
            yield line if decode_unicode else line.encode("utf-8")

    def close(self) -> None:
        self.closed = True

    def json(self) -> dict:
        if self._json_payload is None:
            raise ValueError("json payload missing")
        return self._json_payload


class _FakeTextResponse:
    def __init__(self, text: str, encoding: str = "utf-8") -> None:
        self.content = text.encode(encoding, errors="ignore")

    def raise_for_status(self) -> None:
        return None

    def close(self) -> None:
        return None


class _CustomStaticPlugin:
    def __init__(self, price: float = 11.1) -> None:
        self.price = price

    def next_quote(self, _feed: EastmoneySSEExtendedFeed):
        return {"price": self.price}


def test_eastmoney_sse_ext_feed_reuses_stream_across_ticks() -> None:
    calls = {"n": 0}

    def fake_get(*_args, **_kwargs):
        calls["n"] += 1
        return _FakeResponse(
            [
                'data: {"content":{"price":10.01,"volume":100}}',
                'data: {"content":{"price":10.02,"volume":110}}',
            ]
        )

    feed = EastmoneySSEExtendedFeed(
        symbol="600000",
        sse_url="https://example.com/sse",
        get_request=fake_get,
        max_ticks=2,
        max_reconnects=0,
        backoff_seconds=0.0,
    )
    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    feed.next()
    bus.dispatch()
    feed.next()
    bus.dispatch()

    assert calls["n"] == 1
    assert [ev.fields["close"] for ev in captured] == [10.01, 10.02]


def test_eastmoney_sse_ext_feed_reconnects_after_stream_end() -> None:
    calls = {"n": 0}

    def fake_get(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeResponse(['data: {"content":{"price":9.9}}'])
        return _FakeResponse(['data: {"content":{"price":10.0}}'])

    feed = EastmoneySSEExtendedFeed(
        symbol="600000",
        sse_url="https://example.com/sse",
        get_request=fake_get,
        max_ticks=2,
        max_reconnects=1,
        backoff_seconds=0.0,
    )
    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    feed.next()
    bus.dispatch()
    feed.next()
    bus.dispatch()

    assert calls["n"] == 2
    assert [ev.fields["close"] for ev in captured] == [9.9, 10.0]


def test_eastmoney_sse_ext_feed_supports_snapshot_api_plugin_fallback() -> None:
    calls: list[str] = []

    def fake_get(url: str, **_kwargs):
        calls.append(url)
        if "example.com/sse" in url:
            return _FakeResponse(['data: {"type":"next_seq","seq":12,"content":""}'])
        return _FakeResponse([], json_payload={"data": {"f43": 1005}})

    feed = EastmoneySSEExtendedFeed(
        symbol="600000",
        get_request=fake_get,
        max_ticks=1,
        max_reconnects=0,
        backoff_seconds=0.0,
        sources=[
            {"type": "sse", "sse_url": "https://example.com/sse"},
            {
                "type": "snapshot_api",
                "snapshot_url": "https://example.com/snapshot",
                "on_demand_only": True,
            },
        ],
    )
    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    feed.next()
    bus.dispatch()

    assert len(captured) == 1
    assert captured[0].fields["close"] == 10.05
    assert any("example.com/snapshot" in u for u in calls)


def test_eastmoney_sse_ext_feed_switches_to_snapshot_immediately_on_next_seq() -> None:
    calls: list[str] = []

    def fake_get(url: str, **_kwargs):
        calls.append(url)
        if "example.com/sse" in url:
            return _FakeResponse(
                [
                    'data: {"type":"next_seq","seq":12,"content":""}',
                    'data: {"content":{"price":88.88}}',
                ]
            )
        return _FakeResponse([], json_payload={"data": {"f43": 1007}})

    feed = EastmoneySSEExtendedFeed(
        symbol="600000",
        get_request=fake_get,
        max_ticks=1,
        max_reconnects=0,
        backoff_seconds=0.0,
        sources=[
            {"type": "sse", "sse_url": "https://example.com/sse"},
            {
                "type": "snapshot_api",
                "snapshot_url": "https://example.com/snapshot",
                "on_demand_only": True,
            },
        ],
    )
    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    feed.next()
    bus.dispatch()

    assert len(captured) == 1
    assert captured[0].fields["close"] == 10.07
    assert any("example.com/snapshot" in u for u in calls)


def test_eastmoney_sse_ext_feed_supports_custom_plugin_class_path() -> None:
    feed = EastmoneySSEExtendedFeed(
        symbol="600000",
        max_ticks=1,
        max_reconnects=0,
        backoff_seconds=0.0,
        sources=[
            {
                "type": "plugin",
                "class_path": "tests.test_eastmoney_sse_ext_feed._CustomStaticPlugin",
                "params": {"price": 12.34},
            }
        ],
    )
    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    feed.next()
    bus.dispatch()

    assert len(captured) == 1
    assert captured[0].fields["close"] == 12.34


def test_eastmoney_sse_ext_feed_supports_sse_field_map_paths() -> None:
    def fake_get(*_args, **_kwargs):
        return _FakeResponse(
            ['data: {"payload":{"quote":{"cur":"10.01","vol":"123","amt":"456"}}}']
        )

    feed = EastmoneySSEExtendedFeed(
        symbol="600000",
        get_request=fake_get,
        max_ticks=1,
        max_reconnects=0,
        backoff_seconds=0.0,
        sources=[
            {
                "type": "sse",
                "sse_url": "https://example.com/sse",
                "field_map": {
                    "price": "payload.quote.cur",
                    "volume": "payload.quote.vol",
                    "amount": "payload.quote.amt",
                },
            }
        ],
    )
    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    feed.next()
    bus.dispatch()

    assert len(captured) == 1
    assert captured[0].fields["close"] == 10.01
    assert captured[0].fields["volume"] == 123.0
    assert captured[0].fields["amount"] == 456.0


def test_eastmoney_sse_ext_feed_supports_snapshot_field_map_and_scale() -> None:
    def fake_get(url: str, **_kwargs):
        if "example.com/sse" in url:
            return _FakeResponse(['data: {"type":"next_seq","seq":13,"content":""}'])
        return _FakeResponse(
            [], json_payload={"result": {"last": 1005, "v": 7, "a": 9}}
        )

    feed = EastmoneySSEExtendedFeed(
        symbol="600000",
        get_request=fake_get,
        max_ticks=1,
        max_reconnects=0,
        backoff_seconds=0.0,
        sources=[
            {"type": "sse", "sse_url": "https://example.com/sse"},
            {
                "type": "snapshot_api",
                "snapshot_url": "https://example.com/snapshot",
                "on_demand_only": True,
                "field_map": {
                    "price": "result.last",
                    "price_scale": 100,
                    "volume": "result.v",
                    "amount": "result.a",
                },
            },
        ],
    )
    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    feed.next()
    bus.dispatch()

    assert len(captured) == 1
    assert captured[0].fields["close"] == 10.05
    assert captured[0].fields["volume"] == 7.0
    assert captured[0].fields["amount"] == 9.0


def test_composable_quote_feed_alias_is_usable() -> None:
    feed = ComposableQuoteFeed(
        symbol="600000",
        max_ticks=1,
        max_reconnects=0,
        backoff_seconds=0.0,
        sources=[
            {
                "type": "plugin",
                "class_path": "tests.test_eastmoney_sse_ext_feed._CustomStaticPlugin",
                "params": {"price": 21.0},
            }
        ],
    )
    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    feed.next()
    bus.dispatch()

    assert len(captured) == 1
    assert captured[0].fields["close"] == 21.0


def test_eastmoney_sse_ext_feed_accepts_snapshot_source_alias() -> None:
    def fake_get(url: str, **_kwargs):
        if "example.com/sse" in url:
            return _FakeResponse(['data: {"type":"next_seq","seq":22,"content":""}'])
        return _FakeResponse([], json_payload={"data": {"f43": 1006}})

    feed = EastmoneySSEExtendedFeed(
        symbol="600000",
        get_request=fake_get,
        max_ticks=1,
        max_reconnects=0,
        backoff_seconds=0.0,
        sources=[
            {"type": "sse", "sse_url": "https://example.com/sse"},
            {
                "type": "snapshot",
                "snapshot_url": "https://example.com/snapshot",
                "on_demand_only": True,
            },
        ],
    )
    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    feed.next()
    bus.dispatch()

    assert len(captured) == 1
    assert captured[0].fields["close"] == 10.06


def test_eastmoney_sse_ext_feed_respects_string_enabled_flag() -> None:
    feed = EastmoneySSEExtendedFeed(
        symbol="600000",
        max_ticks=1,
        max_reconnects=0,
        backoff_seconds=0.0,
        sources=[
            {
                "type": "plugin",
                "class_path": "tests.test_eastmoney_sse_ext_feed._CustomStaticPlugin",
                "params": {"price": 99.0},
                "enabled": "false",
            },
            {
                "type": "plugin",
                "class_path": "tests.test_eastmoney_sse_ext_feed._CustomStaticPlugin",
                "params": {"price": 22.0},
                "enabled": "true",
            },
        ],
    )
    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    feed.next()
    bus.dispatch()

    assert len(captured) == 1
    assert captured[0].fields["close"] == 22.0


def test_eastmoney_sse_ext_feed_supports_api_source_sina_mode() -> None:
    seen: dict[str, str] = {}

    def fake_get(url: str, **_kwargs):
        seen["url"] = url
        return _FakeTextResponse(
            'var hq_str_sh600000="浦发银行,9.980,9.980,9.890,10.030,9.880,9.890,9.900,'
            '70040725,696614490.000";',
            encoding="gbk",
        )

    feed = EastmoneySSEExtendedFeed(
        symbol="600000",
        get_request=fake_get,
        max_ticks=1,
        max_reconnects=0,
        backoff_seconds=0.0,
        sources=[
            {
                "type": "api",
                "url": "https://hq.sinajs.cn/list={symbol}",
                "response_mode": "sina_hq",
                "symbol_transform": "cn_prefix",
                "field_map": {
                    "price": "3",
                    "volume": "8",
                    "amount": "9",
                },
            }
        ],
    )
    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    feed.next()
    bus.dispatch()

    assert "sh600000" in seen["url"]
    assert len(captured) == 1
    assert captured[0].fields["close"] == 9.89
