from __future__ import annotations

from datetime import datetime, timedelta

from pybt.core.event_bus import EventBus
from pybt.core.events import MarketEvent, StrategyDebugEvent
from pybt.strategies import MovingAverageCrossStrategy


def test_moving_average_emits_debug_events_when_enabled() -> None:
    bus = EventBus()
    strategy = MovingAverageCrossStrategy(
        symbol="AAA",
        short_window=2,
        long_window=3,
        debug_signal=True,
    )
    strategy.bind(bus)

    debug_events: list[StrategyDebugEvent] = []
    bus.subscribe(StrategyDebugEvent, debug_events.append)

    base = datetime(2024, 1, 1)
    prices = [10.0, 10.5, 11.0, 10.8]
    for idx, price in enumerate(prices):
        strategy.on_market(
            MarketEvent(
                timestamp=base + timedelta(days=idx),
                symbol="AAA",
                fields={"close": price},
            )
        )
        bus.dispatch()

    assert debug_events
    assert any(ev.stage == "signal" for ev in debug_events)
