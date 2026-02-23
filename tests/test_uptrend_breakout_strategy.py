from datetime import datetime, timedelta

from pybt.core.event_bus import EventBus
from pybt.core.events import MarketEvent, SignalEvent, StrategyDebugEvent
from pybt.strategies.uptrend import UptrendBreakoutStrategy


def test_uptrend_breakout_emits_long_and_exit() -> None:
    bus = EventBus()
    strategy = UptrendBreakoutStrategy(symbol="ABC", window=3, breakout_factor=0.2)
    strategy.bind(bus)

    signals: list[SignalEvent] = []
    bus.subscribe(SignalEvent, signals.append)

    base = datetime(2024, 1, 1)
    prices = [10.0, 10.2, 11.0, 10.0]
    for idx, price in enumerate(prices):
        event = MarketEvent(timestamp=base + timedelta(days=idx), symbol="ABC", fields={"close": price})
        strategy.on_market(event)
        bus.dispatch()

    assert any(sig.direction.name == "LONG" for sig in signals)
    assert any(sig.direction.name == "EXIT" for sig in signals)


def test_uptrend_breakout_emits_debug_events_when_enabled() -> None:
    bus = EventBus()
    strategy = UptrendBreakoutStrategy(
        symbol="ABC", window=3, breakout_factor=0.2, debug_signal=True
    )
    strategy.bind(bus)

    debug_events: list[StrategyDebugEvent] = []
    bus.subscribe(StrategyDebugEvent, debug_events.append)

    base = datetime(2024, 1, 1)
    prices = [10.0, 10.2, 11.0]
    for idx, price in enumerate(prices):
        event = MarketEvent(
            timestamp=base + timedelta(days=idx),
            symbol="ABC",
            fields={"close": price},
        )
        strategy.on_market(event)
        bus.dispatch()

    assert debug_events
    assert any(ev.stage in {"warmup", "signal", "hold"} for ev in debug_events)
