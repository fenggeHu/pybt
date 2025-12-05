from datetime import datetime

from pybt.data.rest_feed import RESTPollingFeed
from pybt.core.event_bus import EventBus
from pybt.core.events import MarketEvent


def test_rest_polling_feed_with_custom_fetcher() -> None:
    prices = [10.0, 10.5, 11.0]

    def fake_fetch(_url: str) -> dict:
        return {"price": prices.pop(0)}

    feed = RESTPollingFeed(symbol="AAA", url="http://example.com", poll_interval=0.0, max_ticks=2, fetcher=fake_fetch)
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
