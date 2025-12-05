from datetime import datetime

from pybt.core.event_bus import EventBus
from pybt.core.events import Event, MarketEvent, SignalEvent
from pybt.core.enums import SignalDirection


def test_event_bus_preserves_publish_order() -> None:
    bus = EventBus()
    seen: list[Event] = []
    bus.subscribe(Event, seen.append)

    e1 = MarketEvent(timestamp=datetime(2024, 1, 1), symbol="A", fields={"close": 1.0})
    e2 = MarketEvent(timestamp=datetime(2024, 1, 2), symbol="A", fields={"close": 2.0})
    bus.publish(e1)
    bus.publish(e2)
    bus.dispatch()

    assert seen == [e1, e2]


def test_event_bus_processes_events_published_during_dispatch() -> None:
    bus = EventBus()
    processed: list[str] = []

    def handle_market(event: MarketEvent) -> None:
        processed.append(event.symbol)
        # Publish another event during dispatch; should be handled after current loop.
        bus.publish(
            SignalEvent(
                timestamp=event.timestamp,
                strategy_id="s",
                symbol="B",
                direction=SignalDirection.LONG,
            )
        )

    def handle_signal(event: SignalEvent) -> None:
        processed.append(event.symbol)

    bus.subscribe(MarketEvent, handle_market)
    bus.subscribe(SignalEvent, handle_signal)

    bus.publish(MarketEvent(timestamp=datetime(2024, 1, 1), symbol="A", fields={"close": 1.0}))
    bus.dispatch()

    assert processed == ["A", "B"]
