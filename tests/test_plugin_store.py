from __future__ import annotations
from pathlib import Path

import pytest

from apps.server.plugin_store import PluginStore
from pybt.configuration.config_file import loads_jsonc


def _write_registry(path: Path) -> None:
    path.write_text(
        """{
  "version": 1,
  "plugin_dir": ".",
  // plugin registry comment should be preserved
  "plugins": [
    {
      "name": "moving_average",
      "kind": "strategy",
      "module": "moving_average",
      "entry": "create",
      "enabled": true,
      "summary": "ma strategy"
    },
    {
      "name": "sina_marketdata",
      "kind": "data_feed",
      "module": "sina_marketdata",
      "entry": "create",
      "enabled": false,
      "summary": "sina api"
    }
  ]
}
""",
        encoding="utf-8",
    )


def test_plugin_store_list_and_filter(tmp_path: Path) -> None:
    path = tmp_path / "plugin.jsonc"
    _write_registry(path)
    store = PluginStore(path)

    all_items = store.list()
    assert len(all_items) == 2
    assert {x["name"] for x in all_items} == {"moving_average", "sina_marketdata"}

    enabled_only = store.list(enabled=True)
    assert len(enabled_only) == 1
    assert enabled_only[0]["name"] == "moving_average"

    strategy_only = store.list(kind="strategy")
    assert len(strategy_only) == 1
    assert strategy_only[0]["name"] == "moving_average"


def test_plugin_store_set_enabled_updates_registry(tmp_path: Path) -> None:
    path = tmp_path / "plugin.jsonc"
    _write_registry(path)
    store = PluginStore(path)

    loaded = store.set_enabled("sina_marketdata", enabled=True)
    assert loaded["enabled"] is True

    payload = loads_jsonc(path.read_text(encoding="utf-8"))
    plugins = payload["plugins"]
    found = next(x for x in plugins if x["name"] == "sina_marketdata")
    assert found["enabled"] is True


def test_plugin_store_set_enabled_preserves_comments(tmp_path: Path) -> None:
    path = tmp_path / "plugin.jsonc"
    _write_registry(path)
    store = PluginStore(path)
    before = path.read_text(encoding="utf-8")
    assert "// plugin registry comment should be preserved" in before

    store.set_enabled("moving_average", enabled=False)

    after = path.read_text(encoding="utf-8")
    assert "// plugin registry comment should be preserved" in after
    assert '"enabled": false' in after


def test_plugin_store_set_enabled_missing_plugin_raises_key_error(tmp_path: Path) -> None:
    path = tmp_path / "plugin.jsonc"
    _write_registry(path)
    store = PluginStore(path)
    with pytest.raises(KeyError):
        store.set_enabled("not_exists", enabled=False)
