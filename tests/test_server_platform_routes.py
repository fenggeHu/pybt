from __future__ import annotations

from fastapi.testclient import TestClient

import apps.server.app as app_module
from apps.server.app import create_app
from apps.server.settings import ServerSettings


class _FakeRunManager:
    def __init__(self, *args, **kwargs) -> None:
        self.last_get_signal_kwargs = None

    def compare_runs(self, left_run_id: str, right_run_id: str):
        if left_run_id == "missing":
            raise KeyError(left_run_id)
        return {
            "left_run_id": left_run_id,
            "right_run_id": right_run_id,
            "summary_delta": {"final_equity": 123.0},
            "event_count_delta": {"NotificationIntentEvent": 2},
        }

    def get_signal_events(
        self,
        run_id: str,
        *,
        since_seq: int = 0,
        limit: int = 200,
        strategy_id: str | None = None,
        symbol: str | None = None,
        include_debug: bool = False,
    ):
        if run_id == "missing":
            raise KeyError(run_id)
        self.last_get_signal_kwargs = {
            "run_id": run_id,
            "since_seq": since_seq,
            "limit": limit,
            "strategy_id": strategy_id,
            "symbol": symbol,
            "include_debug": include_debug,
        }
        return 5, [
            {
                "seq": 3,
                "event_type": "NotificationIntentEvent",
                "strategy_id": "mac",
                "symbol": "AAA",
                "direction": "LONG",
            }
        ]


def test_compare_runs_route(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(app_module, "RunManager", _FakeRunManager)
    app = create_app(ServerSettings(base_dir=tmp_path, api_key="k"))
    client = TestClient(app)

    resp = client.get("/runs/r1/compare/r2", headers={"X-API-Key": "k"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["comparison"]["summary_delta"]["final_equity"] == 123.0


def test_compare_runs_route_not_found(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(app_module, "RunManager", _FakeRunManager)
    app = create_app(ServerSettings(base_dir=tmp_path, api_key="k"))
    client = TestClient(app)

    resp = client.get("/runs/missing/compare/r2", headers={"X-API-Key": "k"})
    assert resp.status_code == 404
    data = resp.json()
    assert data["ok"] is False
    assert data["error"]["code"] == "run_not_found"


def test_signal_debug_route(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(app_module, "RunManager", _FakeRunManager)
    app = create_app(ServerSettings(base_dir=tmp_path, api_key="k"))
    client = TestClient(app)

    resp = client.get(
        "/runs/r1/signals",
        headers={"X-API-Key": "k"},
        params={"since_seq": 2, "limit": 50, "strategy_id": "mac", "include_debug": "true"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["last_seq"] == 5
    assert len(data["signals"]) == 1
    assert data["signals"][0]["event_type"] == "NotificationIntentEvent"
