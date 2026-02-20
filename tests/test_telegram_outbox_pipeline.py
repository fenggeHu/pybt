from apps.telegram_bot.telegram_bot import _event_dedupe_key, _queue_event_for_delivery
from pybt.live.notify import NotificationOutbox


def test_event_dedupe_key_prefers_intent_key() -> None:
    ev = {
        "event_type": "NotificationIntentEvent",
        "seq": 99,
        "data": {"dedupe_key": "intent:abc"},
    }
    key = _event_dedupe_key(run_id="run-1", ev=ev)
    assert key == "intent:abc"


def test_event_dedupe_key_falls_back_to_run_seq_type() -> None:
    ev = {
        "event_type": "FillEvent",
        "seq": 42,
        "data": {"symbol": "AAA"},
    }
    key = _event_dedupe_key(run_id="run-1", ev=ev)
    assert key == "run-1:42:FillEvent"


def test_queue_event_for_delivery_enqueues_formatted_message(tmp_path) -> None:
    outbox = NotificationOutbox(tmp_path / "outbox.sqlite3")
    ev = {
        "event_type": "NotificationIntentEvent",
        "seq": 7,
        "data": {
            "dedupe_key": "intent:run-1:mac:AAA",
            "message": "SIGNAL AAA LONG strength=1",
        },
    }

    queued = _queue_event_for_delivery(
        outbox=outbox,
        run_id="run-1",
        chat_id=1234,
        ev=ev,
    )

    assert queued is True
    claimed = outbox.claim_pending(
        limit=10, now=__import__("datetime").datetime(2024, 1, 1, 10, 0, 0)
    )
    assert len(claimed) == 1
    payload = claimed[0].payload
    assert payload["chat_id"] == 1234
    assert payload["text"] == "SIGNAL AAA LONG strength=1"
