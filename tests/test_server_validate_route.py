from datetime import datetime

from fastapi.testclient import TestClient

from apps.server.app import create_app
from apps.server.settings import ServerSettings


def _valid_config() -> dict:
    return {
        "name": "validate-demo",
        "data_feed": {
            "type": "inmemory",
            "bars": [
                {
                    "symbol": "AAA",
                    "timestamp": datetime(2024, 1, 1, 9, 30).isoformat(),
                    "open": 100,
                    "high": 101,
                    "low": 99,
                    "close": 100.5,
                    "volume": 1000,
                    "amount": 100500,
                }
            ],
        },
        "strategies": [
            {
                "type": "moving_average",
                "symbol": "AAA",
                "short_window": 2,
                "long_window": 3,
            }
        ],
        "portfolio": {"type": "naive", "lot_size": 100, "initial_cash": 100000},
        "execution": {"type": "immediate", "slippage": 0.0, "commission": 0.0},
        "risk": [{"type": "max_position", "limit": 1000}],
        "reporters": [{"type": "equity"}],
    }


def test_validate_route_not_shadowed_by_config_name(tmp_path) -> None:
    app = create_app(ServerSettings(base_dir=tmp_path, api_key="k"))
    client = TestClient(app)

    resp = client.post(
        "/configs/validate",
        headers={"X-API-Key": "k"},
        json={"config": _valid_config()},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True


def test_health_returns_boolean_ok(tmp_path) -> None:
    app = create_app(ServerSettings(base_dir=tmp_path, api_key="k"))
    client = TestClient(app)

    resp = client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True


def test_definitions_route_requires_auth_and_returns_items(tmp_path) -> None:
    app = create_app(ServerSettings(base_dir=tmp_path, api_key="k"))
    client = TestClient(app)

    unauth = client.get("/definitions")
    assert unauth.status_code == 401

    resp = client.get("/definitions", headers={"X-API-Key": "k"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert isinstance(data["definitions"], list)
    assert data["definitions"], "definitions should not be empty"
