from __future__ import annotations

import json
from pathlib import Path

import pytest

from pybt import load_engine_from_dict, load_engine_from_json
from pybt.data.rest_feed import ComposableQuoteFeed, RESTPollingFeed


def _plugin_registry_path() -> Path:
    return Path(__file__).resolve().parent.parent / "plugins" / "plugin.jsonc"


def _write_csv(tmp_path: Path) -> Path:
    path = tmp_path / "AAA" / "Bar.csv"
    path.parent.mkdir(parents=True)
    path.write_text(
        """date,open,high,low,close,volume,amount
2024-01-01,10,11,9,10.5,1000,10000
2024-01-02,10.5,11.5,10,11,1200,13200
""",
        encoding="utf-8",
    )
    return path


def _base_config(csv_path: Path) -> dict:
    return {
        "name": "cfg-demo",
        "plugin_registry": str(_plugin_registry_path()),
        "data_feed": {
            "plugin": "local_csv_feed",
            "params": {"path": str(csv_path), "symbol": "AAA"},
        },
        "strategies": [
            {
                "plugin": "moving_average",
                "params": {
                    "symbol": "AAA",
                    "short_window": 1,
                    "long_window": 2,
                },
            }
        ],
        "portfolio": {
            "plugin": "naive_portfolio",
            "params": {"lot_size": 100, "initial_cash": 10_000},
        },
        "execution": {
            "plugin": "immediate_execution",
            "params": {"slippage": 0.0, "commission": 0.0},
        },
        "risk": [{"plugin": "max_position_risk", "params": {"limit": 200}}],
        "reporters": [{"plugin": "equity_reporter", "params": {"initial_cash": 10_000}}],
    }


def test_load_engine_from_dict_runs_end_to_end(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)

    engine = load_engine_from_dict(cfg)
    engine.run()


def test_load_engine_from_dict_uses_default_plugin_registry(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)
    cfg.pop("plugin_registry", None)

    engine = load_engine_from_dict(cfg)
    engine.run()


def test_load_engine_from_json_runs_end_to_end(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    engine = load_engine_from_json(cfg_path)
    engine.run()


def test_load_engine_from_json_supports_jsonc_refs(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    parts = tmp_path / "parts"
    parts.mkdir()
    (parts / "data_feed.jsonc").write_text(
        f"""
        {{
          "plugin": "local_csv_feed",
          "params": {{"path": "{csv_path}", "symbol": "AAA"}}
        }}
        """,
        encoding="utf-8",
    )
    (parts / "strategy_main.jsonc").write_text(
        """
        {
          "plugin": "moving_average",
          "params": {"symbol": "AAA", "short_window": 1, "long_window": 2},
          "enabled": true
        }
        """,
        encoding="utf-8",
    )
    (parts / "strategy_disabled.jsonc").write_text(
        """
        {
          "plugin": "moving_average",
          "enabled": false
        }
        """,
        encoding="utf-8",
    )
    profile = tmp_path / "profile.jsonc"
    profile.write_text(
        f"""
        {{
          "name": "jsonc-profile",
          "plugin_registry": "{_plugin_registry_path()}",
          "data_feed": {{"$ref": "./parts/data_feed.jsonc"}},
          "strategies": [
            {{"$ref": "./parts/strategy_main.jsonc"}},
            {{"$ref": "./parts/strategy_disabled.jsonc"}}
          ],
          "portfolio": {{"plugin": "naive_portfolio", "params": {{"initial_cash": 10000}}}},
          "execution": {{"plugin": "immediate_execution"}},
          "reporters": [{{"plugin": "equity_reporter"}}]
        }}
        """,
        encoding="utf-8",
    )

    engine = load_engine_from_json(profile)
    assert len(engine.strategies) == 1
    engine.run()


def test_load_engine_from_dict_supports_refs_with_base_dir(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    parts = tmp_path / "parts"
    parts.mkdir()
    (parts / "data_feed.jsonc").write_text(
        f"""
        {{
          "plugin": "local_csv_feed",
          "params": {{"path": "{csv_path}", "symbol": "AAA"}}
        }}
        """,
        encoding="utf-8",
    )
    cfg = {
        "name": "dict-ref-demo",
        "plugin_registry": str(_plugin_registry_path()),
        "data_feed": {"$ref": "./parts/data_feed.jsonc"},
        "strategies": [
            {
                "plugin": "moving_average",
                "params": {"symbol": "AAA", "short_window": 1, "long_window": 2},
            }
        ],
        "portfolio": {
            "plugin": "naive_portfolio",
            "params": {"initial_cash": 10000},
        },
        "execution": {"plugin": "immediate_execution"},
        "reporters": [{"plugin": "equity_reporter"}],
    }

    engine = load_engine_from_dict(cfg, config_base_dir=tmp_path)
    engine.run()


def test_load_engine_from_json_requires_keys(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        load_engine_from_json(cfg_path, plugin_registry_path=_plugin_registry_path())


def test_load_engine_from_dict_requires_strategies_array(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)
    cfg["strategies"] = "not-an-array"

    with pytest.raises(ValueError, match="strategies must be an array"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_requires_strategy_item_object(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)
    cfg["strategies"] = ["bad-item"]

    with pytest.raises(ValueError, match=r"strategies\[0\] must be an object"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_requires_reporters_array(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)
    cfg["reporters"] = {"plugin": "equity_reporter"}

    with pytest.raises(ValueError, match="reporters must be an array"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_ignores_disabled_strategies(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)
    cfg["strategies"] = [
        {"plugin": "moving_average", "enabled": False},
        {
            "plugin": "uptrend",
            "params": {"symbol": "AAA", "window": 2},
        },
    ]

    engine = load_engine_from_dict(cfg)
    assert len(engine.strategies) == 1


def test_load_engine_from_dict_rejects_plugin_kind_mismatch(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)
    cfg["data_feed"] = {"plugin": "moving_average", "params": {"symbol": "AAA"}}

    with pytest.raises(ValueError, match="PLUGIN_KIND_MISMATCH"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_rejects_unknown_plugin(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)
    cfg["data_feed"] = {"plugin": "does_not_exist"}

    with pytest.raises(ValueError, match="PLUGIN_NOT_FOUND"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_rejects_missing_required_plugin_param(
    tmp_path: Path,
) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)
    cfg["strategies"] = [{"plugin": "moving_average", "params": {"short_window": 2}}]

    with pytest.raises(ValueError, match="PLUGIN_INVALID_PARAMS"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_rejects_empty_required_string_param(
    tmp_path: Path,
) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)
    cfg["strategies"] = [{"plugin": "moving_average", "params": {"symbol": "   "}}]

    with pytest.raises(ValueError, match="PLUGIN_INVALID_PARAMS"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_coerces_typed_plugin_params(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)
    cfg["strategies"] = [
        {
            "plugin": "moving_average",
            "params": {
                "symbol": "AAA",
                "short_window": "1",
                "long_window": "2",
            },
        }
    ]
    cfg["portfolio"] = {
        "plugin": "naive_portfolio",
        "params": {"lot_size": "200", "initial_cash": "10000"},
    }

    engine = load_engine_from_dict(cfg)
    assert len(engine.strategies) == 1
    assert engine.portfolio.lot_size == 200
    assert engine.portfolio.initial_cash == 10000.0


def test_load_engine_from_dict_rejects_invalid_typed_plugin_param(
    tmp_path: Path,
) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)
    cfg["strategies"] = [
        {
            "plugin": "moving_average",
            "params": {
                "symbol": "AAA",
                "short_window": "not_int",
                "long_window": 2,
            },
        }
    ]

    with pytest.raises(ValueError, match="PLUGIN_INVALID_PARAMS"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_rejects_unknown_strict_plugin_param(
    tmp_path: Path,
) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)
    cfg["strategies"] = [
        {
            "plugin": "moving_average",
            "params": {
                "symbol": "AAA",
                "unknown_key": 1,
            },
        }
    ]

    with pytest.raises(ValueError, match="PLUGIN_INVALID_PARAMS"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_suggests_closest_param_name(
    tmp_path: Path,
) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)
    cfg["strategies"] = [
        {
            "plugin": "moving_average",
            "params": {
                "symbol": "AAA",
                "short_windwo": 1,
            },
        }
    ]

    with pytest.raises(ValueError, match=r"did you mean 'short_window'"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_supports_rest_polling_plugin(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)
    cfg["data_feed"] = {
        "plugin": "rest_polling_feed",
        "params": {
            "symbol": "AAA",
            "url": "https://example.com/quote",
            "max_retries": 5,
            "backoff_seconds": 0.2,
            "request_timeout": {"connect": 1.0, "read": 2.0},
        },
    }

    engine = load_engine_from_dict(cfg)
    assert isinstance(engine.data_feed, RESTPollingFeed)
    assert engine.data_feed.max_retries == 5
    assert engine.data_feed.backoff_seconds == 0.2
    assert engine.data_feed.request_timeout == (1.0, 2.0)


def test_load_engine_from_dict_supports_marketdata_plugins(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)
    cfg["data_feed"] = {
        "plugin": "eastmoney_marketdata",
        "params": {"symbol": "600000", "transport": "api", "url": "https://example.com"},
    }
    engine = load_engine_from_dict(cfg)
    assert isinstance(engine.data_feed, ComposableQuoteFeed)

    cfg["data_feed"] = {
        "plugin": "sina_marketdata",
        "params": {"symbol": "600000"},
    }
    engine = load_engine_from_dict(cfg)
    assert isinstance(engine.data_feed, ComposableQuoteFeed)


def test_load_engine_from_dict_rejects_unsupported_transport(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)
    cfg["data_feed"] = {
        "plugin": "sina_marketdata",
        "params": {"symbol": "600000", "transport": "sse"},
    }

    with pytest.raises(ValueError, match="PLUGIN_UNSUPPORTED_TRANSPORT"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_rejects_unknown_strict_feed_param(
    tmp_path: Path,
) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = _base_config(csv_path)
    cfg["data_feed"] = {
        "plugin": "sina_marketdata",
        "params": {"symbol": "600000", "transport": "api", "oops": 1},
    }

    with pytest.raises(ValueError, match="PLUGIN_INVALID_PARAMS"):
        load_engine_from_dict(cfg)
