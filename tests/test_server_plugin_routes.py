from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import apps.server.app as app_module
from apps.server.app import create_app
from apps.server.settings import ServerSettings


class _FakeRunManager:
    def __init__(self, *args, **kwargs) -> None:
        pass


class _FakePluginStore:
    def __init__(self, registry_path: Path | None = None) -> None:
        self.registry_path = Path("/tmp/plugin.jsonc")
        self._plugins: dict[str, dict[str, Any]] = {
            "moving_average": {
                "name": "moving_average",
                "kind": "strategy",
                "enabled": True,
                "summary": "MA strategy",
                "module": "moving_average",
                "entry": "create",
            },
            "sina_marketdata": {
                "name": "sina_marketdata",
                "kind": "data_feed",
                "enabled": False,
                "summary": "sina feed",
                "module": "sina_marketdata",
                "entry": "create",
            },
        }

    def list(self, *, kind=None, enabled=None):
        out = list(self._plugins.values())
        if kind is not None:
            out = [x for x in out if x["kind"] == kind]
        if enabled is not None:
            out = [x for x in out if x["enabled"] is enabled]
        return out

    def set_enabled(self, name: str, *, enabled: bool):
        if name not in self._plugins:
            raise KeyError(name)
        self._plugins[name]["enabled"] = enabled
        return dict(self._plugins[name])


def test_list_plugins_route(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(app_module, "RunManager", _FakeRunManager)
    monkeypatch.setattr(app_module, "PluginStore", _FakePluginStore)
    app = create_app(ServerSettings(base_dir=tmp_path, api_key="k"))
    client = TestClient(app)

    resp = client.get("/plugins", headers={"X-API-Key": "k"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert len(payload["plugins"]) == 2

    filtered = client.get(
        "/plugins",
        headers={"X-API-Key": "k"},
        params={"kind": "strategy", "enabled": "true"},
    )
    assert filtered.status_code == 200
    items = filtered.json()["plugins"]
    assert len(items) == 1
    assert items[0]["name"] == "moving_average"


def test_plugin_load_unload_routes(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(app_module, "RunManager", _FakeRunManager)
    monkeypatch.setattr(app_module, "PluginStore", _FakePluginStore)
    app = create_app(ServerSettings(base_dir=tmp_path, api_key="k"))
    client = TestClient(app)

    load_resp = client.post("/plugins/sina_marketdata/load", headers={"X-API-Key": "k"})
    assert load_resp.status_code == 200
    assert load_resp.json()["plugin"]["enabled"] is True

    unload_resp = client.post("/plugins/moving_average/unload", headers={"X-API-Key": "k"})
    assert unload_resp.status_code == 200
    assert unload_resp.json()["plugin"]["enabled"] is False


def test_plugin_route_not_found_and_invalid_kind(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(app_module, "RunManager", _FakeRunManager)
    monkeypatch.setattr(app_module, "PluginStore", _FakePluginStore)
    app = create_app(ServerSettings(base_dir=tmp_path, api_key="k"))
    client = TestClient(app)

    not_found = client.post("/plugins/nope/load", headers={"X-API-Key": "k"})
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "plugin_not_found"

    bad_kind = client.get(
        "/plugins",
        headers={"X-API-Key": "k"},
        params={"kind": "invalid_kind"},
    )
    assert bad_kind.status_code == 400
    assert bad_kind.json()["error"]["code"] == "plugin_invalid_request"
