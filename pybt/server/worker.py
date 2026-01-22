from __future__ import annotations

import json
import traceback
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from pybt.config import load_engine_from_dict
from pybt.core.events import FillEvent, MetricsEvent


def _dt_to_iso(dt: datetime) -> str:
    return dt.isoformat()


def _serialize_event(event: object) -> tuple[str, str, dict[str, Any]]:
    event_type = event.__class__.__name__
    timestamp = getattr(event, "timestamp", None)
    ts = timestamp.isoformat() if isinstance(timestamp, datetime) else ""
    data: dict[str, Any] = {}
    if is_dataclass(event):
        raw = asdict(event)  # type: ignore
        # Convert datetime fields to iso strings for JSON and IPC safety.
        for k, v in list(raw.items()):
            if isinstance(v, datetime):
                raw[k] = v.isoformat()
        data = raw
    return event_type, ts, data


def run_worker(run_id: str, config: Mapping[str, Any], run_dir_str: str, event_q: Any) -> None:
    run_dir = Path(run_dir_str)
    try:
        engine = load_engine_from_dict(config)

        def on_fill(ev: FillEvent) -> None:
            et, ts, data = _serialize_event(ev)
            event_q.put({"kind": "event", "event_type": et, "timestamp": ts, "data": data})

        def on_metrics(ev: MetricsEvent) -> None:
            et, ts, data = _serialize_event(ev)
            event_q.put({"kind": "event", "event_type": et, "timestamp": ts, "data": data})

        engine.bus.subscribe(FillEvent, on_fill)
        engine.bus.subscribe(MetricsEvent, on_metrics)

        engine.run()

        # Best-effort summary extraction.
        summary = None
        for reporter in getattr(engine, "reporters", []):
            if hasattr(reporter, "get_summary"):
                try:
                    summary = reporter.get_summary()  # type: ignore[attr-defined]
                except Exception:
                    summary = None
                break

        if summary is not None:
            (run_dir / "summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        event_q.put({"kind": "final", "state": "completed", "summary": summary})
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
        (run_dir / "error.txt").write_text(
            err + "\n\n" + traceback.format_exc(), encoding="utf-8"
        )
        event_q.put({"kind": "error", "error": err})
