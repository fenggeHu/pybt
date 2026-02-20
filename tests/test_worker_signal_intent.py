import queue
from datetime import datetime

from apps.server import worker as worker_module
from pybt.core.enums import SignalDirection
from pybt.core.event_bus import EventBus
from pybt.core.events import SignalEvent


class _FakeEngine:
    def __init__(self) -> None:
        self.bus = EventBus()
        self.reporters: list[object] = []

    def run(self) -> None:
        self.bus.publish(
            SignalEvent(
                timestamp=datetime(2024, 1, 1, 10, 0),
                strategy_id="plugin",
                symbol="AAA",
                direction=SignalDirection.LONG,
                strength=0.8,
            )
        )
        self.bus.dispatch()


def test_worker_emits_notification_intent_event(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        worker_module, "load_engine_from_dict", lambda _cfg: _FakeEngine()
    )

    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    event_q: queue.Queue = queue.Queue()

    worker_module.run_worker("run-abc", {}, str(run_dir), event_q)

    messages = []
    while not event_q.empty():
        messages.append(event_q.get_nowait())

    intent_messages = [
        m
        for m in messages
        if isinstance(m, dict)
        and m.get("kind") == "event"
        and m.get("event_type") == "NotificationIntentEvent"
    ]
    assert intent_messages, "expected worker to emit NotificationIntentEvent"
    data = intent_messages[0]["data"]
    assert data["intent_type"] == "strategy_signal"
    assert data["run_id"] == "run-abc"
    assert data["strategy_id"] == "plugin"
    assert data["symbol"] == "AAA"
    assert data["direction"] == "LONG"
