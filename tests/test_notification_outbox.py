from datetime import datetime, timedelta
from pathlib import Path

from pybt.live.notify import NotificationOutbox


def test_outbox_enqueue_and_claim_roundtrip(tmp_path: Path) -> None:
    outbox = NotificationOutbox(tmp_path / "outbox.sqlite3")

    payload = {
        "intent_type": "strategy_signal",
        "symbol": "AAA",
        "direction": "LONG",
        "dedupe_key": "run-1:mac:AAA:1:LONG",
    }

    message_id = outbox.enqueue(
        event_type="NotificationIntentEvent",
        payload=payload,
        dedupe_key=payload["dedupe_key"],
    )

    claimed = outbox.claim_pending(limit=10, now=datetime(2024, 1, 1, 9, 30, 0))
    assert len(claimed) == 1
    assert claimed[0].id == message_id
    assert claimed[0].event_type == "NotificationIntentEvent"
    assert claimed[0].payload["symbol"] == "AAA"
    assert claimed[0].attempt_count == 1


def test_outbox_dedupe_key_is_idempotent(tmp_path: Path) -> None:
    outbox = NotificationOutbox(tmp_path / "outbox.sqlite3")
    payload = {
        "intent_type": "strategy_signal",
        "symbol": "BBB",
        "direction": "SHORT",
        "dedupe_key": "run-1:mac:BBB:2:SHORT",
    }

    first = outbox.enqueue(
        event_type="NotificationIntentEvent",
        payload=payload,
        dedupe_key=payload["dedupe_key"],
    )
    second = outbox.enqueue(
        event_type="NotificationIntentEvent",
        payload=payload,
        dedupe_key=payload["dedupe_key"],
    )

    assert first == second
    assert outbox.total_count() == 1


def test_outbox_retry_window_controls_reclaim(tmp_path: Path) -> None:
    outbox = NotificationOutbox(tmp_path / "outbox.sqlite3")
    payload = {
        "intent_type": "strategy_signal",
        "symbol": "CCC",
        "direction": "EXIT",
        "dedupe_key": "run-1:up:CCC:3:EXIT",
    }
    message_id = outbox.enqueue(
        event_type="NotificationIntentEvent",
        payload=payload,
        dedupe_key=payload["dedupe_key"],
    )

    t0 = datetime(2024, 1, 1, 10, 0, 0)
    claimed = outbox.claim_pending(limit=1, now=t0)
    assert claimed and claimed[0].id == message_id

    outbox.mark_failed(
        message_id,
        error="rate_limit",
        retry_delay_seconds=30,
        now=t0,
        max_attempts=3,
    )

    not_ready = outbox.claim_pending(limit=1, now=t0 + timedelta(seconds=10))
    assert not not_ready

    ready = outbox.claim_pending(limit=1, now=t0 + timedelta(seconds=31))
    assert ready and ready[0].id == message_id
    assert ready[0].attempt_count == 2


def test_outbox_marks_dead_letter_after_max_attempts(tmp_path: Path) -> None:
    outbox = NotificationOutbox(tmp_path / "outbox.sqlite3")
    payload = {
        "intent_type": "strategy_signal",
        "symbol": "DDD",
        "direction": "LONG",
        "dedupe_key": "run-1:up:DDD:4:LONG",
    }
    message_id = outbox.enqueue(
        event_type="NotificationIntentEvent",
        payload=payload,
        dedupe_key=payload["dedupe_key"],
    )

    now = datetime(2024, 1, 1, 11, 0, 0)
    outbox.claim_pending(limit=1, now=now)
    outbox.mark_failed(
        message_id,
        error="timeout",
        retry_delay_seconds=0,
        now=now,
        max_attempts=1,
    )

    assert outbox.status_of(message_id) == "dead_letter"


def test_outbox_persists_messages_across_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "outbox.sqlite3"
    first = NotificationOutbox(db_path)
    payload = {
        "intent_type": "strategy_signal",
        "symbol": "FFF",
        "direction": "LONG",
        "dedupe_key": "run-1:up:FFF:5:LONG",
    }
    message_id = first.enqueue(
        event_type="NotificationIntentEvent",
        payload=payload,
        dedupe_key=payload["dedupe_key"],
    )

    second = NotificationOutbox(db_path)
    claimed = second.claim_pending(limit=10, now=datetime(2024, 1, 1, 12, 0, 0))
    assert len(claimed) == 1
    assert claimed[0].id == message_id


def test_outbox_reclaims_stale_sending_message(tmp_path: Path) -> None:
    outbox = NotificationOutbox(tmp_path / "outbox.sqlite3")
    payload = {
        "intent_type": "strategy_signal",
        "symbol": "GGG",
        "direction": "LONG",
        "dedupe_key": "run-1:up:GGG:6:LONG",
    }
    message_id = outbox.enqueue(
        event_type="NotificationIntentEvent",
        payload=payload,
        dedupe_key=payload["dedupe_key"],
    )

    t0 = datetime(2024, 1, 1, 12, 0, 0)
    first_claim = outbox.claim_pending(limit=1, now=t0)
    assert first_claim and first_claim[0].id == message_id

    stale_claim = outbox.claim_pending(limit=1, now=t0 + timedelta(seconds=61))
    assert stale_claim and stale_claim[0].id == message_id
    assert stale_claim[0].attempt_count == 2
