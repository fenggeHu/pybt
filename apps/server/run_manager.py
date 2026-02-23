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
    event_counts: dict[str, int] = None  # type: ignore[assignment]
    process: Optional[Any] = None
    event_queue: Optional[Any] = None

    def __post_init__(self) -> None:
        if self.events is None:
            self.events = deque(maxlen=2000)
        if self.event_counts is None:
            self.event_counts = {}


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

    @staticmethod
    def _events_log_path(run_dir: Path) -> Path:
        return run_dir / "events.jsonl"

    @staticmethod
    def _manifest_path(run_dir: Path) -> Path:
        return run_dir / "manifest.json"

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
            self._persist_manifest(rec)

            proc.start()
            rec.pid = proc.pid
            rec.state = "running"
            self._persist_manifest(rec)

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
            rec.event_counts[event_type] = rec.event_counts.get(event_type, 0) + 1
            rec.events.append(
                EventEnvelope(
                    seq=rec.last_seq,
                    received_at=_utc_now(),
                    event_type=event_type,
                    timestamp=timestamp,
                    data=data,
                )
            )
            self._append_event_log(
                rec=rec,
                event_type=event_type,
                timestamp=timestamp,
                data=data,
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
                            self._persist_manifest(rec)
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
                    self._persist_manifest(rec)
            elif kind == "error":
                with self._lock:
                    rec = self._runs.get(run_id)
                    if rec is None:
                        return
                    rec.state = "failed"
                    rec.error = msg.get("error", "unknown error")
                    rec.ended_at = _utc_now()
                    self._persist_manifest(rec)

    def compare_runs(self, left_run_id: str, right_run_id: str) -> dict[str, Any]:
        with self._lock:
            left = self._runs.get(left_run_id)
            right = self._runs.get(right_run_id)
            if left is None:
                raise KeyError(left_run_id)
            if right is None:
                raise KeyError(right_run_id)

            summary_delta = self._summary_delta(left.summary, right.summary)
            event_delta = self._event_count_delta(left.event_counts, right.event_counts)
            return {
                "left_run_id": left_run_id,
                "right_run_id": right_run_id,
                "left_state": left.state,
                "right_state": right.state,
                "left_last_seq": left.last_seq,
                "right_last_seq": right.last_seq,
                "event_count_delta": event_delta,
                "summary_delta": summary_delta,
            }

    def get_signal_events(
        self,
        run_id: str,
        *,
        since_seq: int = 0,
        limit: int = 200,
        strategy_id: Optional[str] = None,
        symbol: Optional[str] = None,
        include_debug: bool = False,
    ) -> tuple[int, list[dict[str, Any]]]:
        with self._lock:
            rec = self._runs.get(run_id)
            if rec is None:
                raise KeyError(run_id)

            selected: list[dict[str, Any]] = []
            for ev in list(rec.events):
                if ev.seq <= since_seq:
                    continue
                if ev.event_type == "NotificationIntentEvent":
                    item = self._normalize_signal_item(ev)
                elif include_debug and ev.event_type == "StrategyDebugEvent":
                    item = self._normalize_debug_item(ev)
                else:
                    continue
                if item is None:
                    continue
                if strategy_id and item.get("strategy_id") != strategy_id:
                    continue
                if symbol and item.get("symbol") != symbol:
                    continue
                selected.append(item)
            if limit > 0:
                selected = selected[-limit:]
            return rec.last_seq, selected

    def _normalize_signal_item(self, ev: EventEnvelope) -> Optional[dict[str, Any]]:
        data = ev.data
        if not isinstance(data, Mapping):
            return None
        return {
            "seq": ev.seq,
            "event_type": ev.event_type,
            "received_at": ev.received_at.isoformat(),
            "timestamp": ev.timestamp,
            "strategy_id": str(data.get("strategy_id", "")),
            "symbol": str(data.get("symbol", "")),
            "direction": str(data.get("direction", "")),
            "strength": data.get("strength"),
            "message": str(data.get("message", "")),
            "meta": dict(data.get("meta", {})) if isinstance(data.get("meta"), Mapping) else {},
        }

    def _normalize_debug_item(self, ev: EventEnvelope) -> Optional[dict[str, Any]]:
        data = ev.data
        if not isinstance(data, Mapping):
            return None
        return {
            "seq": ev.seq,
            "event_type": ev.event_type,
            "received_at": ev.received_at.isoformat(),
            "timestamp": ev.timestamp,
            "strategy_id": str(data.get("strategy_id", "")),
            "symbol": str(data.get("symbol", "")),
            "stage": str(data.get("stage", "")),
            "message": str(data.get("message", "")),
            "details": (
                dict(data.get("details", {}))
                if isinstance(data.get("details"), Mapping)
                else {}
            ),
        }

    def _append_event_log(
        self,
        *,
        rec: RunRecord,
        event_type: str,
        timestamp: str,
        data: Mapping[str, Any],
    ) -> None:
        path = self._events_log_path(rec.run_dir)
        row = {
            "seq": rec.last_seq,
            "received_at": rec.events[-1].received_at.isoformat(),
            "event_type": event_type,
            "timestamp": timestamp,
            "data": dict(data),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _persist_manifest(self, rec: RunRecord) -> None:
        payload = {
            "run_id": rec.run_id,
            "config_name": rec.config_name,
            "state": rec.state,
            "pid": rec.pid,
            "started_at": rec.started_at.isoformat(),
            "ended_at": rec.ended_at.isoformat() if rec.ended_at else None,
            "error": rec.error,
            "last_seq": rec.last_seq,
            "event_counts": dict(rec.event_counts),
            "has_summary": rec.summary is not None,
        }
        self._manifest_path(rec.run_dir).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _event_count_delta(
        left: Mapping[str, int], right: Mapping[str, int]
    ) -> dict[str, int]:
        keys = sorted(set(left.keys()) | set(right.keys()))
        out: dict[str, int] = {}
        for key in keys:
            out[key] = int(right.get(key, 0)) - int(left.get(key, 0))
        return out

    @staticmethod
    def _summary_delta(
        left: Optional[Mapping[str, Any]], right: Optional[Mapping[str, Any]]
    ) -> dict[str, Any]:
        if not isinstance(left, Mapping) or not isinstance(right, Mapping):
            return {}
        out: dict[str, Any] = {}
        keys = sorted(set(left.keys()) & set(right.keys()))
        for key in keys:
            lv = left.get(key)
            rv = right.get(key)
            if isinstance(lv, (int, float)) and isinstance(rv, (int, float)):
                out[key] = float(rv) - float(lv)
        return out
