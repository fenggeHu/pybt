from fastapi.testclient import TestClient
from enum import Enum

from apps.server.app import ErrorCode, ErrorHint, create_app
from apps.server.settings import ServerSettings


def _client(tmp_path) -> TestClient:
    app = create_app(ServerSettings(base_dir=tmp_path, api_key="k"))
    return TestClient(app)


def test_auth_error_has_structured_payload_and_request_id(tmp_path) -> None:
    client = _client(tmp_path)

    resp = client.get("/configs")

    assert resp.status_code == 401
    rid = resp.headers.get("x-request-id")
    assert isinstance(rid, str) and rid

    body = resp.json()
    assert body["ok"] is False
    err = body["error"]
    assert err["code"] == "auth_invalid_api_key"
    assert err["message"] == "invalid api key"
    assert err["hint"] == "Provide X-API-Key header"
    assert err["request_id"] == rid


def test_error_propagates_incoming_request_id(tmp_path) -> None:
    client = _client(tmp_path)

    resp = client.get(
        "/configs/missing.json",
        headers={"X-API-Key": "k", "X-Request-ID": "req-123"},
    )

    assert resp.status_code == 404
    assert resp.headers.get("x-request-id") == "req-123"
    body = resp.json()
    assert body["ok"] is False
    err = body["error"]
    assert err["code"] == "config_not_found"
    assert err["request_id"] == "req-123"
    assert err["details"]["name"] == "missing.json"


def test_create_run_request_shape_error_has_actionable_hint(tmp_path) -> None:
    client = _client(tmp_path)

    resp = client.post("/runs", headers={"X-API-Key": "k"}, json={})

    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["code"] == "invalid_run_request"
    assert err["hint"] == "Send either config_name or config, but not both."


def test_run_not_found_error_has_recovery_hint(tmp_path) -> None:
    client = _client(tmp_path)

    resp = client.get("/runs/missing-run", headers={"X-API-Key": "k"})

    assert resp.status_code == 404
    err = resp.json()["error"]
    assert err["code"] == "run_not_found"
    assert err["hint"] == "Check /runs for available run IDs."


def test_websocket_run_not_found_error_has_recovery_hint(tmp_path) -> None:
    client = _client(tmp_path)

    with client.websocket_connect(
        "/runs/missing-run/stream", headers={"x-api-key": "k"}
    ) as ws:
        msg = ws.receive_json()

    assert msg["kind"] == "error"
    err = msg["error"]
    assert err["code"] == "run_not_found"
    assert err["hint"] == "Check /runs for available run IDs."


def test_error_contract_codes_and_hints_use_enum_types() -> None:
    assert issubclass(ErrorCode, Enum)
    assert issubclass(ErrorHint, Enum)
    assert ErrorCode.RUN_NOT_FOUND.value == "run_not_found"
    assert ErrorHint.CHECK_RUNS.value == "Check /runs for available run IDs."


def test_websocket_invalid_api_key_returns_structured_error(tmp_path) -> None:
    client = _client(tmp_path)

    with client.websocket_connect(
        "/runs/any/stream", headers={"x-api-key": "bad"}
    ) as ws:
        msg = ws.receive_json()

    assert msg["kind"] == "error"
    err = msg["error"]
    assert err["code"] == "auth_invalid_api_key"
    assert err["hint"] == "Provide X-API-Key header"
    assert isinstance(err["request_id"], str) and err["request_id"]
