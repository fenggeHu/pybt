from datetime import datetime
from inspect import isawaitable
from math import ceil
from typing import Any, Callable

from .outbox import NotificationOutbox, OutboxMessage


class OutboxNotifierWorker:
    def __init__(
        self,
        *,
        outbox: NotificationOutbox,
        sender: Callable[[OutboxMessage], Any],
        retry_delay_seconds: int,
        max_attempts: int,
    ) -> None:
        self.outbox = outbox
        self.sender = sender
        self.retry_delay_seconds = retry_delay_seconds
        self.max_attempts = max_attempts

    def _compute_retry_delay(self, message: OutboxMessage, exc: Exception) -> int:
        base = max(1, int(self.retry_delay_seconds))
        exp = max(0, message.attempt_count - 1)
        delay = base * (2**exp)

        retry_after = getattr(exc, "retry_after", None)
        if isinstance(retry_after, (int, float)) and retry_after > 0:
            hinted = int(ceil(float(retry_after)))
            if hinted > delay:
                delay = hinted
        return delay

    def process_once(self, *, limit: int, now: datetime) -> dict[str, int]:
        claimed = self.outbox.claim_pending(limit=limit, now=now)
        sent = 0
        failed = 0
        for message in claimed:
            try:
                self.sender(message)
            except Exception as exc:
                failed += 1
                self.outbox.mark_failed(
                    message.id,
                    error=f"{type(exc).__name__}: {exc}",
                    retry_delay_seconds=self._compute_retry_delay(message, exc),
                    now=now,
                    max_attempts=self.max_attempts,
                )
            else:
                sent += 1
                self.outbox.mark_sent(message.id, now=now)
        return {"claimed": len(claimed), "sent": sent, "failed": failed}

    async def process_once_async(self, *, limit: int, now: datetime) -> dict[str, int]:
        claimed = self.outbox.claim_pending(limit=limit, now=now)
        sent = 0
        failed = 0
        for message in claimed:
            try:
                result = self.sender(message)
                if isawaitable(result):
                    await result
            except Exception as exc:
                failed += 1
                self.outbox.mark_failed(
                    message.id,
                    error=f"{type(exc).__name__}: {exc}",
                    retry_delay_seconds=self._compute_retry_delay(message, exc),
                    now=now,
                    max_attempts=self.max_attempts,
                )
            else:
                sent += 1
                self.outbox.mark_sent(message.id, now=now)
        return {"claimed": len(claimed), "sent": sent, "failed": failed}
