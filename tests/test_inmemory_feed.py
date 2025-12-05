from datetime import datetime

from pybt.core.event_bus import EventBus
from pybt.core.events import MarketEvent
from pybt.data.feeds import InMemoryBarFeed
from pybt.core.models import Bar


def test_inmemory_feed_publishes_sorted_events() -> None:
    bar1 = Bar(symbol="AAA", timestamp=datetime(2024, 1, 2), open=1, high=2, low=0.5, close=1.5, volume=10)
    bar0 = Bar(symbol="AAA", timestamp=datetime(2024, 1, 1), open=1, high=2, low=0.5, close=1.4, volume=8)
    feed = InMemoryBarFeed([bar1, bar0])
    bus = EventBus()
    feed.bind(bus)

    captured: list[MarketEvent] = []
    bus.subscribe(MarketEvent, captured.append)

    feed.prime()
    while feed.has_next():
        feed.next()
        bus.dispatch()

    assert [e.timestamp for e in captured] == [bar0.timestamp, bar1.timestamp]
