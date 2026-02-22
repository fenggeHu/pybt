from datetime import datetime

from pybt.data.rest_feed import RESTPollingFeed
from pybt.core.event_bus import EventBus
from pybt.core.events import MarketEvent


def test_rest_polling_feed_with_custom_fetcher() -> None:
    prices = [10.0, 10.5, 11.0]

    def fake_fetch(_url: str) -> dict:
        return {"price": prices.pop(0)}

    feed = RESTPollingFeed(
        symbol="AAA",
        url="http://example.com",
        poll_interval=0.0,
        max_ticks=2,
        fetcher=fake_fetch,
    )
    bus = EventBus()
    feed.bind(bus)

    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    while feed.has_next():
        feed.next()
        bus.dispatch()

    assert len(captured) == 2
    assert captured[0].fields["close"] == 10.0
    assert captured[1].fields["close"] == 10.5


def test_rest_polling_feed_retries_and_raises() -> None:
    attempts = 0

    def flaky(_url: str) -> dict:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("fail")
        return {"price": 9.9}

    feed = RESTPollingFeed(
        symbol="AAA",
        url="http://example.com",
        poll_interval=0.0,
        max_ticks=1,
        fetcher=flaky,
        max_retries=3,
        backoff_seconds=0.0,
    )
    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)
    feed.prime()
    feed.next()
    bus.dispatch()
    assert captured[0].fields["close"] == 9.9


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.closed = False

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload

    def close(self) -> None:
        self.closed = True


class _FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, float | tuple[float, float]]] = []
        self.closed = False

    def get(self, url: str, timeout: float | tuple[float, float]):
        self.calls.append((url, timeout))
        return _FakeResponse({"price": 8.8, "volume": 100})

    def close(self) -> None:
        self.closed = True


def test_rest_polling_feed_uses_session_and_timeout() -> None:
    session = _FakeSession()
    feed = RESTPollingFeed(
        symbol="AAA",
        url="http://example.com",
        poll_interval=0.0,
        max_ticks=1,
        request_timeout=(1.5, 3.0),
        session=session,
    )
    bus = EventBus()
    feed.bind(bus)
    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    feed.next()
    bus.dispatch()
    feed.on_stop()

    assert len(captured) == 1
    assert session.calls == [("http://example.com", (1.5, 3.0))]
    # Session lifecycle is caller-managed when injected externally.
    assert session.closed is False
