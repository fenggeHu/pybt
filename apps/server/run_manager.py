from __future__ import annotations

import json
import queue
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Mapping, Optional
from uuid import uuid4

import multiprocessing as mp

from .worker import run_worker


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class EventEnvelope:
    seq: int
    received_at: datetime
    event_type: str
    timestamp: str
    data: Mapping[str, Any]


@dataclass
class RunRecord:
    run_id: str
    config_name: str
    run_dir: Path
    started_at: datetime
    state: str = "starting"
    pid: Optional[int] = None
    ended_at: Optional[datetime] = None
    error: Optional[str] = None
    summary: Optional[Mapping[str, Any]] = None
    last_seq: int = 0
    events: Deque[EventEnvelope] = None  # type: ignore[assignment]
    process: Optional[Any] = None
    event_queue: Optional[Any] = None

    def __post_init__(self) -> None:
        if self.events is None:
            self.events = deque(maxlen=2000)


class RunManager:
    def __init__(self, *, runs_dir: Path, max_concurrent_runs: int) -> None:
        self.runs_dir = runs_dir
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.max_concurrent_runs = max_concurrent_runs
        self._lock = threading.Lock()
        self._runs: dict[str, RunRecord] = {}

    def list(self) -> list[RunRecord]:
        with self._lock:
            return list(self._runs.values())

    def get(self, run_id: str) -> RunRecord:
        with self._lock:
            rec = self._runs.get(run_id)
            if rec is None:
                raise KeyError(run_id)
            return rec

    def get_events(
        self,
        run_id: str,
        *,
        since_seq: int,
        limit: int,
        event_type: Optional[str] = None,
    ) -> tuple[int, list[EventEnvelope]]:
        """Return (last_seq, events) snapshot for a run.

        This is intentionally lock-protected to avoid races with the background
        queue consumer thread.
        """

        with self._lock:
            rec = self._runs.get(run_id)
            if rec is None:
                raise KeyError(run_id)
            selected: list[EventEnvelope] = []
            for ev in list(rec.events):
                if ev.seq <= since_seq:
                    continue
                if event_type is not None and ev.event_type != event_type:
                    continue
                selected.append(ev)
            if limit > 0:
                selected = selected[-limit:]
            return rec.last_seq, selected

    def _running_count(self) -> int:
        return sum(1 for r in self._runs.values() if r.state in {"starting", "running"})

    def start(self, *, config_name: str, config: Mapping[str, Any]) -> RunRecord:
        with self._lock:
            if self._running_count() >= self.max_concurrent_runs:
                raise RuntimeError("Too many concurrent runs")

            run_id = uuid4().hex[:10]
            run_dir = self.runs_dir / run_id
            run_dir.mkdir(parents=True, exist_ok=False)
            (run_dir / "config.json").write_text(
                json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

            ctx = mp.get_context("spawn")
            event_q: mp.Queue = ctx.Queue(maxsize=5000)
            proc = ctx.Process(
                target=run_worker,
                args=(run_id, config, str(run_dir), event_q),
                name=f"pybt-run-{run_id}",
                daemon=True,
            )

            rec = RunRecord(
                run_id=run_id,
                config_name=config_name,
                run_dir=run_dir,
                started_at=_utc_now(),
                process=proc,
                event_queue=event_q,
            )
            self._runs[run_id] = rec

            proc.start()
            rec.pid = proc.pid
            rec.state = "running"

            t = threading.Thread(target=self._consume_events, args=(run_id,), daemon=True)
            t.start()
            return rec

    def stop_hard(self, run_id: str) -> None:
        with self._lock:
            rec = self._runs.get(run_id)
            if rec is None:
                raise KeyError(run_id)
            proc = rec.process
            if proc is None or (not proc.is_alive()):
                return
            rec.state = "stopped"
            proc.terminate()

    def append_event(self, run_id: str, *, event_type: str, timestamp: str, data: Mapping[str, Any]) -> None:
        with self._lock:
            rec = self._runs.get(run_id)
            if rec is None:
                raise KeyError(run_id)
            rec.last_seq += 1
            rec.events.append(
                EventEnvelope(
                    seq=rec.last_seq,
                    received_at=_utc_now(),
                    event_type=event_type,
                    timestamp=timestamp,
                    data=data,
                )
            )

    def _consume_events(self, run_id: str) -> None:
        # Avoid holding the lock while blocking on Queue.get().
        with self._lock:
            rec = self._runs.get(run_id)
            if rec is None:
                return
            q = rec.event_queue
        if q is None:
            return

        while True:
            # If worker died and queue is empty, finalize.
            with self._lock:
                proc = rec.process
                ended_at = rec.ended_at
            if proc is not None and (not proc.is_alive()):
                try:
                    msg = q.get_nowait()
                except queue.Empty:
                    if ended_at is None:
                        with self._lock:
                            rec = self._runs.get(run_id)
                            if rec is None:
                                return
                            rec.ended_at = _utc_now()
                            if rec.state in {"running", "starting"}:
                                # No explicit final message. Infer from exit code.
                                if proc.exitcode and proc.exitcode != 0:
                                    rec.state = "failed"
                                    rec.error = rec.error or f"worker exitcode={proc.exitcode}"
                                else:
                                    rec.state = "completed"
                    return
            try:
                msg = q.get(timeout=0.25)
            except queue.Empty:
                continue

            kind = msg.get("kind")
            if kind == "event":
                self.append_event(
                    run_id,
                    event_type=msg.get("event_type", "Event"),
                    timestamp=msg.get("timestamp", ""),
                    data=msg.get("data", {}),
                )
            elif kind == "final":
                with self._lock:
                    rec = self._runs.get(run_id)
                    if rec is None:
                        return
                    rec.state = msg.get("state", rec.state)
                    rec.summary = msg.get("summary")
                    rec.error = msg.get("error")
                    rec.ended_at = _utc_now()
            elif kind == "error":
                with self._lock:
                    rec = self._runs.get(run_id)
                    if rec is None:
                        return
                    rec.state = "failed"
                    rec.error = msg.get("error", "unknown error")
                    rec.ended_at = _utc_now()
