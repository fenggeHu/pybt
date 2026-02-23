from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from apps.server.run_manager import EventEnvelope, RunManager, RunRecord


def _make_record(tmp_path: Path, run_id: str) -> RunRecord:
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return RunRecord(
        run_id=run_id,
        config_name="cfg",
        run_dir=run_dir,
        started_at=datetime.now(timezone.utc),
    )


def test_compare_runs_returns_event_and_summary_delta(tmp_path: Path) -> None:
    mgr = RunManager(runs_dir=tmp_path / "runs", max_concurrent_runs=2)
    left = _make_record(tmp_path, "left")
    right = _make_record(tmp_path, "right")
    left.state = "completed"
    right.state = "completed"
    left.event_counts = {"NotificationIntentEvent": 2, "MetricsEvent": 10}
    right.event_counts = {"NotificationIntentEvent": 5, "MetricsEvent": 8}
    left.summary = {"final_equity": 100_000.0, "total_return": 0.01, "non_numeric": "x"}
    right.summary = {"final_equity": 103_000.0, "total_return": 0.03, "non_numeric": "y"}

    mgr._runs[left.run_id] = left  # noqa: SLF001 - test setup
    mgr._runs[right.run_id] = right  # noqa: SLF001 - test setup

    out = mgr.compare_runs("left", "right")
    assert out["event_count_delta"]["NotificationIntentEvent"] == 3
    assert out["event_count_delta"]["MetricsEvent"] == -2
    assert out["summary_delta"]["final_equity"] == 3000.0
    assert out["summary_delta"]["total_return"] == pytest.approx(0.02)
    assert "non_numeric" not in out["summary_delta"]


def test_get_signal_events_supports_debug_filtering(tmp_path: Path) -> None:
    mgr = RunManager(runs_dir=tmp_path / "runs", max_concurrent_runs=2)
    rec = _make_record(tmp_path, "r1")
    rec.last_seq = 2
    rec.events.append(
        EventEnvelope(
            seq=1,
            received_at=datetime.now(timezone.utc),
            event_type="NotificationIntentEvent",
            timestamp="2024-01-01T00:00:00+00:00",
            data={
                "strategy_id": "mac",
                "symbol": "AAA",
                "direction": "LONG",
                "strength": 1.2,
                "message": "signal",
                "meta": {"short_ma": 11.1},
            },
        )
    )
    rec.events.append(
        EventEnvelope(
            seq=2,
            received_at=datetime.now(timezone.utc),
            event_type="StrategyDebugEvent",
            timestamp="2024-01-01T00:00:01+00:00",
            data={
                "strategy_id": "mac",
                "symbol": "AAA",
                "stage": "hold",
                "message": "no crossover",
                "details": {"short_ma": 11.1, "long_ma": 11.2},
            },
        )
    )
    mgr._runs[rec.run_id] = rec  # noqa: SLF001 - test setup

    _, signals_only = mgr.get_signal_events(rec.run_id, include_debug=False)
    assert len(signals_only) == 1
    assert signals_only[0]["event_type"] == "NotificationIntentEvent"

    _, with_debug = mgr.get_signal_events(rec.run_id, include_debug=True)
    assert len(with_debug) == 2
    assert with_debug[1]["event_type"] == "StrategyDebugEvent"
    assert with_debug[1]["stage"] == "hold"


def test_append_event_persists_jsonl_log(tmp_path: Path) -> None:
    mgr = RunManager(runs_dir=tmp_path / "runs", max_concurrent_runs=2)
    rec = _make_record(tmp_path, "r-log")
    mgr._runs[rec.run_id] = rec  # noqa: SLF001 - test setup

    mgr.append_event(
        rec.run_id,
        event_type="NotificationIntentEvent",
        timestamp="2024-01-01T00:00:00+00:00",
        data={"strategy_id": "mac", "symbol": "AAA", "direction": "LONG"},
    )

    path = rec.run_dir / "events.jsonl"
    assert path.exists()
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["event_type"] == "NotificationIntentEvent"
    assert rec.event_counts["NotificationIntentEvent"] == 1
