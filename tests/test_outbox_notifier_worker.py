from datetime import datetime, timedelta
from pathlib import Path

import pytest

from pybt.live.notify import NotificationOutbox, OutboxNotifierWorker


def test_worker_marks_sent_on_success(tmp_path: Path) -> None:
    outbox = NotificationOutbox(tmp_path / "outbox.sqlite3")
    payload = {
        "intent_type": "strategy_signal",
        "symbol": "AAA",
        "direction": "LONG",
        "dedupe_key": "run-1:mac:AAA:10:LONG",
    }
    message_id = outbox.enqueue(
        event_type="NotificationIntentEvent",
        payload=payload,
        dedupe_key=payload["dedupe_key"],
    )

    sent = []

    def sender(msg) -> None:
        sent.append(msg.id)

    worker = OutboxNotifierWorker(
        outbox=outbox,
        sender=sender,
        retry_delay_seconds=5,
        max_attempts=3,
    )

    stats = worker.process_once(limit=10, now=datetime(2024, 1, 1, 9, 0, 0))

    assert stats["claimed"] == 1
    assert stats["sent"] == 1
    assert stats["failed"] == 0
    assert sent == [message_id]
    assert outbox.status_of(message_id) == "sent"


def test_worker_retries_after_failure(tmp_path: Path) -> None:
    outbox = NotificationOutbox(tmp_path / "outbox.sqlite3")
    payload = {
        "intent_type": "strategy_signal",
        "symbol": "BBB",
        "direction": "SHORT",
        "dedupe_key": "run-1:mac:BBB:11:SHORT",
    }
    message_id = outbox.enqueue(
        event_type="NotificationIntentEvent",
        payload=payload,
        dedupe_key=payload["dedupe_key"],
    )

    calls = {"count": 0}

    def flaky_sender(_msg) -> None:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary error")

    worker = OutboxNotifierWorker(
        outbox=outbox,
        sender=flaky_sender,
        retry_delay_seconds=10,
        max_attempts=3,
    )

    t0 = datetime(2024, 1, 1, 10, 0, 0)
    first = worker.process_once(limit=10, now=t0)
    assert first["claimed"] == 1
    assert first["sent"] == 0
    assert first["failed"] == 1
    assert outbox.status_of(message_id) == "failed"

    early = worker.process_once(limit=10, now=t0 + timedelta(seconds=5))
    assert early["claimed"] == 0

    second = worker.process_once(limit=10, now=t0 + timedelta(seconds=11))
    assert second["claimed"] == 1
    assert second["sent"] == 1
    assert second["failed"] == 0
    assert outbox.status_of(message_id) == "sent"


def test_worker_respects_retry_after_hint(tmp_path: Path) -> None:
    outbox = NotificationOutbox(tmp_path / "outbox.sqlite3")
    payload = {
        "intent_type": "strategy_signal",
        "symbol": "EEE",
        "direction": "LONG",
        "dedupe_key": "run-1:mac:EEE:13:LONG",
    }
    message_id = outbox.enqueue(
        event_type="NotificationIntentEvent",
        payload=payload,
        dedupe_key=payload["dedupe_key"],
    )

    class RateLimitError(Exception):
        def __init__(self) -> None:
            super().__init__("rate limited")
            self.retry_after = 30

    def sender(_msg) -> None:
        raise RateLimitError()

    worker = OutboxNotifierWorker(
        outbox=outbox,
        sender=sender,
        retry_delay_seconds=5,
        max_attempts=3,
    )

    t0 = datetime(2024, 1, 1, 13, 0, 0)
    first = worker.process_once(limit=10, now=t0)
    assert first["failed"] == 1
    assert outbox.status_of(message_id) == "failed"

    too_early = worker.process_once(limit=10, now=t0 + timedelta(seconds=20))
    assert too_early["claimed"] == 0

    ready = worker.process_once(limit=10, now=t0 + timedelta(seconds=31))
    assert ready["claimed"] == 1


@pytest.mark.asyncio
async def test_worker_process_once_async_supports_async_sender(tmp_path: Path) -> None:
    outbox = NotificationOutbox(tmp_path / "outbox.sqlite3")
    payload = {
        "intent_type": "strategy_signal",
        "symbol": "CCC",
        "direction": "LONG",
        "dedupe_key": "run-1:mac:CCC:12:LONG",
        "chat_id": 123,
        "text": "hello",
    }
    message_id = outbox.enqueue(
        event_type="NotificationIntentEvent",
        payload=payload,
        dedupe_key=payload["dedupe_key"],
    )

    sent: list[str] = []

    async def async_sender(msg) -> None:
        sent.append(msg.id)

    worker = OutboxNotifierWorker(
        outbox=outbox,
        sender=async_sender,
        retry_delay_seconds=5,
        max_attempts=3,
    )

    stats = await worker.process_once_async(
        limit=10, now=datetime(2024, 1, 1, 12, 0, 0)
    )

    assert stats["claimed"] == 1
    assert stats["sent"] == 1
    assert stats["failed"] == 0
    assert sent == [message_id]
    assert outbox.status_of(message_id) == "sent"
