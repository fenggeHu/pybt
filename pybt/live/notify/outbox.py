import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class OutboxMessage:
    id: str
    event_type: str
    payload: dict[str, Any]
    dedupe_key: str
    status: str
    attempt_count: int
    next_retry_at: Optional[datetime]
    last_error: Optional[str]


class NotificationOutbox:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_outbox (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    dedupe_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    next_retry_at TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_claimed_at TEXT
                )
                """
            )
            conn.commit()

    def enqueue(
        self, *, event_type: str, payload: dict[str, Any], dedupe_key: str
    ) -> str:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM notification_outbox WHERE dedupe_key = ?",
                (dedupe_key,),
            ).fetchone()
            if existing is not None:
                return str(existing["id"])

            now = datetime.utcnow().isoformat()
            message_id = uuid.uuid4().hex
            conn.execute(
                """
                INSERT INTO notification_outbox
                (id, event_type, payload_json, dedupe_key, status, attempt_count, next_retry_at, last_error, created_at, updated_at, last_claimed_at)
                VALUES (?, ?, ?, ?, 'pending', 0, NULL, NULL, ?, ?, NULL)
                """,
                (
                    message_id,
                    event_type,
                    json.dumps(payload, ensure_ascii=False),
                    dedupe_key,
                    now,
                    now,
                ),
            )
            conn.commit()
            return message_id

    def claim_pending(
        self,
        *,
        limit: int,
        now: datetime,
        stale_sending_after_seconds: int = 60,
    ) -> list[OutboxMessage]:
        now_iso = now.isoformat()
        stale_cutoff = (
            now - timedelta(seconds=stale_sending_after_seconds)
        ).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, event_type, payload_json, dedupe_key, status, attempt_count, next_retry_at, last_error
                FROM notification_outbox
                WHERE status = 'pending'
                   OR (status = 'failed' AND (next_retry_at IS NULL OR next_retry_at <= ?))
                   OR (status = 'sending' AND last_claimed_at IS NOT NULL AND last_claimed_at <= ?)
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (now_iso, stale_cutoff, limit),
            ).fetchall()

            out: list[OutboxMessage] = []
            for row in rows:
                new_attempt = int(row["attempt_count"]) + 1
                conn.execute(
                    """
                    UPDATE notification_outbox
                    SET status = 'sending', attempt_count = ?, updated_at = ?, last_claimed_at = ?
                    WHERE id = ?
                    """,
                    (new_attempt, now_iso, now_iso, row["id"]),
                )
                payload = json.loads(str(row["payload_json"]))
                next_retry_at = row["next_retry_at"]
                out.append(
                    OutboxMessage(
                        id=str(row["id"]),
                        event_type=str(row["event_type"]),
                        payload=payload,
                        dedupe_key=str(row["dedupe_key"]),
                        status="sending",
                        attempt_count=new_attempt,
                        next_retry_at=datetime.fromisoformat(next_retry_at)
                        if isinstance(next_retry_at, str)
                        else None,
                        last_error=str(row["last_error"])
                        if row["last_error"] is not None
                        else None,
                    )
                )
            conn.commit()
            return out

    def mark_sent(self, message_id: str, *, now: datetime) -> None:
        now_iso = now.isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE notification_outbox SET status = 'sent', updated_at = ? WHERE id = ?",
                (now_iso, message_id),
            )
            conn.commit()

    def mark_failed(
        self,
        message_id: str,
        *,
        error: str,
        retry_delay_seconds: int,
        now: datetime,
        max_attempts: int,
    ) -> None:
        now_iso = now.isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT attempt_count FROM notification_outbox WHERE id = ?",
                (message_id,),
            ).fetchone()
            if row is None:
                return
            attempt_count = int(row["attempt_count"])
            if attempt_count >= max_attempts:
                conn.execute(
                    """
                    UPDATE notification_outbox
                    SET status = 'dead_letter', next_retry_at = NULL, last_error = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (error, now_iso, message_id),
                )
            else:
                next_retry = (now + timedelta(seconds=retry_delay_seconds)).isoformat()
                conn.execute(
                    """
                    UPDATE notification_outbox
                    SET status = 'failed', next_retry_at = ?, last_error = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (next_retry, error, now_iso, message_id),
                )
            conn.commit()

    def total_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM notification_outbox"
            ).fetchone()
            return int(row["cnt"]) if row is not None else 0

    def status_of(self, message_id: str) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM notification_outbox WHERE id = ?",
                (message_id,),
            ).fetchone()
            if row is None:
                raise KeyError(message_id)
            return str(row["status"])
