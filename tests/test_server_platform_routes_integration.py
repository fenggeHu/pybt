from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
import pytest

import apps.server.app as app_module
from apps.server.app import create_app
from apps.server.run_manager import EventEnvelope, RunManager, RunRecord
from apps.server.settings import ServerSettings


class _SeededRunManager(RunManager):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        now = datetime.now(timezone.utc)

        left = self._new_record("left", now)
        right = self._new_record("right", now)

        left.state = "completed"
        right.state = "completed"
        left.summary = {"final_equity": 100_000.0, "total_return": 0.01}
        right.summary = {"final_equity": 103_000.0, "total_return": 0.03}
        left.event_counts = {"NotificationIntentEvent": 1}
        right.event_counts = {"NotificationIntentEvent": 3, "StrategyDebugEvent": 1}
        left.last_seq = 1
        right.last_seq = 2
        right.events.append(
            EventEnvelope(
                seq=1,
                received_at=now,
                event_type="NotificationIntentEvent",
                timestamp="2026-01-01T00:00:00+00:00",
                data={
                    "strategy_id": "ma",
                    "symbol": "600000",
                    "direction": "LONG",
                    "strength": 1.0,
                    "message": "signal",
                    "meta": {"short_ma": 11.1, "long_ma": 11.0},
                },
            )
        )
        right.events.append(
            EventEnvelope(
                seq=2,
                received_at=now,
                event_type="StrategyDebugEvent",
                timestamp="2026-01-01T00:00:01+00:00",
                data={
                    "strategy_id": "ma",
                    "symbol": "600000",
                    "stage": "hold",
                    "message": "no crossover",
                    "details": {"short_ma": 11.1, "long_ma": 11.2},
                },
            )
        )

        self._runs[left.run_id] = left  # noqa: SLF001 - test fixture setup
        self._runs[right.run_id] = right  # noqa: SLF001 - test fixture setup

    def _new_record(self, run_id: str, started_at: datetime) -> RunRecord:
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return RunRecord(
            run_id=run_id,
            config_name="cfg",
            run_dir=run_dir,
            started_at=started_at,
        )


def test_compare_runs_with_real_manager_logic(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(app_module, "RunManager", _SeededRunManager)
    app = create_app(ServerSettings(base_dir=tmp_path, api_key="k"))
    client = TestClient(app)

    resp = client.get("/runs/left/compare/right", headers={"X-API-Key": "k"})
    assert resp.status_code == 200
    payload = resp.json()["comparison"]
    assert payload["summary_delta"]["final_equity"] == 3000.0
    assert payload["summary_delta"]["total_return"] == pytest.approx(0.02)
    assert payload["event_count_delta"]["NotificationIntentEvent"] == 2
    assert payload["event_count_delta"]["StrategyDebugEvent"] == 1


def test_signal_route_with_real_manager_logic(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(app_module, "RunManager", _SeededRunManager)
    app = create_app(ServerSettings(base_dir=tmp_path, api_key="k"))
    client = TestClient(app)

    resp = client.get(
        "/runs/right/signals",
        headers={"X-API-Key": "k"},
        params={"strategy_id": "ma", "symbol": "600000"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["last_seq"] == 2
    assert len(payload["signals"]) == 1
    assert payload["signals"][0]["event_type"] == "NotificationIntentEvent"

    debug_resp = client.get(
        "/runs/right/signals",
        headers={"X-API-Key": "k"},
        params={"strategy_id": "ma", "symbol": "600000", "include_debug": "true"},
    )
    assert debug_resp.status_code == 200
    debug_payload = debug_resp.json()
    assert len(debug_payload["signals"]) == 2
    assert debug_payload["signals"][1]["event_type"] == "StrategyDebugEvent"
