from datetime import datetime

from pybt.core.enums import SignalDirection
from pybt.core.events import SignalEvent
from pybt.live.bridge import build_signal_notification_event


def test_build_signal_notification_event_shape() -> None:
    ev = SignalEvent(
        timestamp=datetime(2024, 1, 1),
        strategy_id="mac-1",
        symbol="AAA",
        direction=SignalDirection.LONG,
        strength=1.23,
        meta={"short_ma": 10.0, "long_ma": 9.5},
    )

    out = build_signal_notification_event(run_id="run-001", event=ev)

    assert out["event_type"] == "NotificationIntentEvent"
    assert out["timestamp"] == ev.timestamp.isoformat()
    data = out["data"]
    assert data["intent_type"] == "strategy_signal"
    assert data["strategy_id"] == "mac-1"
    assert data["symbol"] == "AAA"
    assert data["direction"] == "LONG"
    assert data["strength"] == 1.23
    assert data["run_id"] == "run-001"
    assert data["dedupe_key"] == "run-001:mac-1:AAA:2024-01-01T00:00:00:LONG"


def test_build_signal_notification_event_without_run_id() -> None:
    ev = SignalEvent(
        timestamp=datetime(2024, 1, 1, 9, 30),
        strategy_id="uptrend",
        symbol="BBB",
        direction=SignalDirection.EXIT,
        strength=0.5,
    )

    out = build_signal_notification_event(run_id=None, event=ev)

    data = out["data"]
    assert data["run_id"] == ""
    assert data["dedupe_key"].startswith(":uptrend:BBB:2024-01-01T09:30:00:EXIT")
