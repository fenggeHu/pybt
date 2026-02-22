from datetime import datetime
from pathlib import Path

import pytest

from pybt import load_engine_from_dict, load_engine_from_json
from pybt.data.rest_feed import (
    ComposableQuoteFeed,
    EastmoneySSEExtendedFeed,
    EastmoneySSEFeed,
    RESTPollingFeed,
)
from pybt.data.websocket_feed import WebSocketJSONFeed


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


def test_load_engine_from_json_runs_end_to_end(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = {
        "name": "cfg-demo",
        "data_feed": {"type": "local_csv", "path": str(csv_path), "symbol": "AAA"},
        "strategies": [
            {
                "type": "moving_average",
                "symbol": "AAA",
                "short_window": 1,
                "long_window": 2,
            }
        ],
        "portfolio": {"type": "naive", "lot_size": 100, "initial_cash": 10_000},
        "execution": {"type": "immediate", "slippage": 0.0, "commission": 0.0},
        "risk": [{"type": "max_position", "limit": 200}],
        "reporters": [{"type": "equity", "initial_cash": 10_000}],
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(__import__("json").dumps(cfg), encoding="utf-8")

    engine = load_engine_from_json(cfg_path)
    engine.run()


def test_load_engine_from_json_supports_jsonc_refs(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    parts = tmp_path / "parts"
    parts.mkdir()
    (parts / "data_feed.jsonc").write_text(
        f"""
        {{
          // local csv feed
          "type": "local_csv",
          "path": "{csv_path}",
          "symbol": "AAA",
        }}
        """,
        encoding="utf-8",
    )
    (parts / "strategy_main.jsonc").write_text(
        """
        {
          "type": "moving_average",
          "symbol": "AAA",
          "short_window": 1,
          "long_window": 2,
          "enabled": true,
        }
        """,
        encoding="utf-8",
    )
    (parts / "strategy_disabled.jsonc").write_text(
        """
        {
          "type": "moving_average",
          // missing symbol is fine because it is disabled and ignored
          "enabled": false,
        }
        """,
        encoding="utf-8",
    )
    profile = tmp_path / "profile.jsonc"
    profile.write_text(
        """
        {
          "name": "jsonc-profile",
          "data_feed": {"$ref": "./parts/data_feed.jsonc"},
          "strategies": [
            {"$ref": "./parts/strategy_main.jsonc"},
            {"$ref": "./parts/strategy_disabled.jsonc"},
          ],
          "portfolio": {"type": "naive", "lot_size": 100, "initial_cash": 10000},
          "execution": {"type": "immediate", "slippage": 0.0, "commission": 0.0},
          "reporters": [{"type": "equity"}],
        }
        """,
        encoding="utf-8",
    )

    engine = load_engine_from_json(profile)
    assert len(engine.strategies) == 1
    engine.run()


def test_load_engine_from_dict_runs_end_to_end(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = {
        "name": "cfg-demo",
        "data_feed": {"type": "local_csv", "path": str(csv_path), "symbol": "AAA"},
        "strategies": [
            {
                "type": "moving_average",
                "symbol": "AAA",
                "short_window": 1,
                "long_window": 2,
            }
        ],
        "portfolio": {"type": "naive", "lot_size": 100, "initial_cash": 10_000},
        "execution": {"type": "immediate", "slippage": 0.0, "commission": 0.0},
        "risk": [{"type": "max_position", "limit": 200}],
        "reporters": [{"type": "equity"}],
    }

    engine = load_engine_from_dict(cfg)
    engine.run()


def test_load_engine_from_dict_supports_additional_risks(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = {
        "name": "cfg-risks",
        "data_feed": {"type": "local_csv", "path": str(csv_path), "symbol": "AAA"},
        "strategies": [
            {
                "type": "moving_average",
                "symbol": "AAA",
                "short_window": 1,
                "long_window": 2,
            }
        ],
        "portfolio": {"type": "naive", "lot_size": 100, "initial_cash": 10_000},
        "execution": {"type": "immediate", "slippage": 0.0, "commission": 0.0},
        "risk": [
            {"type": "price_band", "band_pct": 0.2},
            {"type": "buying_power", "max_leverage": 1.0, "reserve_cash": 0.0},
            {"type": "concentration", "max_fraction": 0.9},
        ],
        "reporters": [{"type": "equity"}],
    }

    engine = load_engine_from_dict(cfg)
    engine.run()


def test_load_engine_from_json_requires_keys(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        load_engine_from_json(cfg_path)


def test_load_engine_from_json_requires_root_object(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="Config JSON must be an object"):
        load_engine_from_json(cfg_path)


def test_load_engine_from_dict_requires_strategies_array(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = {
        "data_feed": {"type": "local_csv", "path": str(csv_path), "symbol": "AAA"},
        "strategies": "not-an-array",
        "portfolio": {"type": "naive"},
        "execution": {"type": "immediate"},
    }

    with pytest.raises(ValueError, match="strategies must be an array"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_requires_strategy_item_object(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = {
        "data_feed": {"type": "local_csv", "path": str(csv_path), "symbol": "AAA"},
        "strategies": ["bad-item"],
        "portfolio": {"type": "naive"},
        "execution": {"type": "immediate"},
    }

    with pytest.raises(ValueError, match=r"strategies\[0\] must be an object"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_requires_reporters_array(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = {
        "data_feed": {"type": "local_csv", "path": str(csv_path), "symbol": "AAA"},
        "strategies": [{"type": "moving_average", "symbol": "AAA"}],
        "portfolio": {"type": "naive"},
        "execution": {"type": "immediate"},
        "reporters": {"type": "equity"},
    }

    with pytest.raises(ValueError, match="reporters must be an array"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_supports_eastmoney_sse_feed() -> None:
    cfg = {
        "name": "cfg-eastmoney",
        "data_feed": {
            "type": "eastmoney_sse",
            "symbol": "600000",
            "sse_url": "https://example.com/sse",
            "max_ticks": 1,
            "backoff_seconds": 0.1,
            "max_reconnects": 1,
        },
        "strategies": [
            {
                "type": "moving_average",
                "symbol": "600000",
                "short_window": 1,
                "long_window": 2,
            }
        ],
        "portfolio": {"type": "naive", "lot_size": 100, "initial_cash": 10_000},
        "execution": {"type": "immediate", "slippage": 0.0, "commission": 0.0},
        "risk": [{"type": "max_position", "limit": 200}],
        "reporters": [{"type": "equity"}],
    }

    engine = load_engine_from_dict(cfg)
    assert isinstance(engine.data_feed, EastmoneySSEFeed)


def test_load_engine_from_dict_supports_rest_feed_advanced_options() -> None:
    cfg = {
        "name": "cfg-rest",
        "data_feed": {
            "type": "rest",
            "symbol": "AAA",
            "url": "https://example.com/quote",
            "poll_interval": 0.5,
            "max_ticks": 1,
            "max_retries": 5,
            "backoff_seconds": 0.2,
            "connect_timeout": 1.0,
            "read_timeout": 2.0,
        },
        "strategies": [
            {
                "type": "moving_average",
                "symbol": "AAA",
                "short_window": 1,
                "long_window": 2,
            }
        ],
        "portfolio": {"type": "naive", "lot_size": 100, "initial_cash": 10_000},
        "execution": {"type": "immediate", "slippage": 0.0, "commission": 0.0},
        "reporters": [{"type": "equity"}],
    }

    engine = load_engine_from_dict(cfg)
    assert isinstance(engine.data_feed, RESTPollingFeed)
    assert engine.data_feed.max_retries == 5
    assert engine.data_feed.backoff_seconds == 0.2
    assert engine.data_feed.request_timeout == (1.0, 2.0)


def test_load_engine_from_dict_supports_rest_feed_timeout_array() -> None:
    cfg = {
        "name": "cfg-rest-timeout-array",
        "data_feed": {
            "type": "rest",
            "symbol": "AAA",
            "url": "https://example.com/quote",
            "request_timeout": [0.8, 1.6],
        },
        "strategies": [{"type": "moving_average", "symbol": "AAA"}],
        "portfolio": {"type": "naive"},
        "execution": {"type": "immediate"},
    }

    engine = load_engine_from_dict(cfg)
    assert isinstance(engine.data_feed, RESTPollingFeed)
    assert engine.data_feed.request_timeout == (0.8, 1.6)


def test_load_engine_from_dict_supports_rest_feed_timeout_object() -> None:
    cfg = {
        "name": "cfg-rest-timeout-object",
        "data_feed": {
            "type": "rest",
            "symbol": "AAA",
            "url": "https://example.com/quote",
            "request_timeout": {"connect": 0.7, "read": 1.4},
        },
        "strategies": [{"type": "moving_average", "symbol": "AAA"}],
        "portfolio": {"type": "naive"},
        "execution": {"type": "immediate"},
    }

    engine = load_engine_from_dict(cfg)
    assert isinstance(engine.data_feed, RESTPollingFeed)
    assert engine.data_feed.request_timeout == (0.7, 1.4)


def test_load_engine_from_dict_rejects_bad_rest_timeout_array_shape() -> None:
    cfg = {
        "name": "cfg-rest-timeout-invalid",
        "data_feed": {
            "type": "rest",
            "symbol": "AAA",
            "url": "https://example.com/quote",
            "request_timeout": [1.0],
        },
        "strategies": [{"type": "moving_average", "symbol": "AAA"}],
        "portfolio": {"type": "naive"},
        "execution": {"type": "immediate"},
    }

    with pytest.raises(ValueError, match="request_timeout array"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_supports_websocket_feed_advanced_options() -> None:
    cfg = {
        "name": "cfg-websocket",
        "data_feed": {
            "type": "websocket",
            "symbol": "AAA",
            "url": "wss://example.com/stream",
            "max_ticks": 10,
            "max_reconnects": 8,
            "backoff_seconds": 1.25,
            "heartbeat_interval": 3.0,
        },
        "strategies": [{"type": "moving_average", "symbol": "AAA"}],
        "portfolio": {"type": "naive"},
        "execution": {"type": "immediate"},
    }

    engine = load_engine_from_dict(cfg)
    assert isinstance(engine.data_feed, WebSocketJSONFeed)
    assert engine.data_feed.max_reconnects == 8
    assert engine.data_feed.backoff_seconds == 1.25
    assert engine.data_feed.heartbeat_interval == 3.0


def test_load_engine_from_dict_supports_eastmoney_sse_ext_feed() -> None:
    cfg = {
        "name": "cfg-eastmoney-ext",
        "data_feed": {
            "type": "eastmoney_sse_ext",
            "symbol": "600000",
            "secid": "1.600000",
            "max_ticks": 1,
            "backoff_seconds": 0.1,
            "max_reconnects": 1,
            "reconnect_every_ticks": 50,
            "heartbeat_timeout": 10.0,
        },
        "strategies": [
            {
                "type": "moving_average",
                "symbol": "600000",
                "short_window": 1,
                "long_window": 2,
            }
        ],
        "portfolio": {"type": "naive", "lot_size": 100, "initial_cash": 10_000},
        "execution": {"type": "immediate", "slippage": 0.0, "commission": 0.0},
        "risk": [{"type": "max_position", "limit": 200}],
        "reporters": [{"type": "equity"}],
    }

    engine = load_engine_from_dict(cfg)
    assert isinstance(engine.data_feed, EastmoneySSEExtendedFeed)


def test_load_engine_from_dict_supports_market_feed_type() -> None:
    cfg = {
        "name": "cfg-market-feed",
        "data_feed": {
            "type": "market_feed",
            "symbol": "600000",
            "secid": "1.600000",
            "max_ticks": 1,
            "backoff_seconds": 0.1,
            "max_reconnects": 1,
            "sources": [
                {"type": "sse", "sse_url": "https://example.com/sse"},
                {
                    "type": "snapshot_api",
                    "snapshot_url": "https://example.com/snapshot",
                    "on_demand_only": True,
                },
            ],
        },
        "strategies": [
            {
                "type": "moving_average",
                "symbol": "600000",
                "short_window": 1,
                "long_window": 2,
            }
        ],
        "portfolio": {"type": "naive", "lot_size": 100, "initial_cash": 10_000},
        "execution": {"type": "immediate", "slippage": 0.0, "commission": 0.0},
        "risk": [{"type": "max_position", "limit": 200}],
        "reporters": [{"type": "equity"}],
    }

    engine = load_engine_from_dict(cfg)
    assert isinstance(engine.data_feed, ComposableQuoteFeed)
    assert isinstance(engine.data_feed, EastmoneySSEExtendedFeed)


def test_load_engine_from_dict_supports_market_feed_simple_source() -> None:
    cfg = {
        "name": "cfg-market-feed-simple",
        "data_feed": {
            "type": "market_feed",
            "symbol": "600000",
            "source": "sse",
            "snapshot_fallback": False,
        },
        "strategies": [{"type": "moving_average", "symbol": "600000"}],
        "portfolio": {"type": "naive"},
        "execution": {"type": "immediate"},
    }

    engine = load_engine_from_dict(cfg)
    assert isinstance(engine.data_feed, ComposableQuoteFeed)
    assert len(engine.data_feed._plugins) == 1


def test_load_engine_from_dict_market_feed_simple_source_rejects_conflict() -> None:
    cfg = {
        "name": "cfg-market-feed-conflict",
        "data_feed": {
            "type": "market_feed",
            "symbol": "600000",
            "source": "sse",
            "sources": [{"type": "sse"}],
        },
        "strategies": [{"type": "moving_average", "symbol": "600000"}],
        "portfolio": {"type": "naive"},
        "execution": {"type": "immediate"},
    }

    with pytest.raises(ValueError, match="data_feed.source"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_market_feed_simple_websocket_requires_url() -> None:
    cfg = {
        "name": "cfg-market-feed-websocket",
        "data_feed": {
            "type": "market_feed",
            "symbol": "600000",
            "source": "websocket",
        },
        "strategies": [{"type": "moving_average", "symbol": "600000"}],
        "portfolio": {"type": "naive"},
        "execution": {"type": "immediate"},
    }

    with pytest.raises(ValueError, match="data_feed.url"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_supports_market_feed_simple_api_source() -> None:
    cfg = {
        "name": "cfg-market-feed-simple-api",
        "data_feed": {
            "type": "market_feed",
            "symbol": "600000",
            "source": "api",
            "url": "https://hq.sinajs.cn/list={symbol}",
            "response_mode": "sina_hq",
            "symbol_transform": "cn_prefix",
            "field_map": {"price": "3", "volume": "8", "amount": "9"},
        },
        "strategies": [{"type": "moving_average", "symbol": "600000"}],
        "portfolio": {"type": "naive"},
        "execution": {"type": "immediate"},
    }

    engine = load_engine_from_dict(cfg)
    assert isinstance(engine.data_feed, ComposableQuoteFeed)
    assert len(engine.data_feed._plugins) == 1


def test_load_engine_from_dict_market_feed_simple_api_requires_url() -> None:
    cfg = {
        "name": "cfg-market-feed-simple-api-no-url",
        "data_feed": {
            "type": "market_feed",
            "symbol": "600000",
            "source": "api",
        },
        "strategies": [{"type": "moving_average", "symbol": "600000"}],
        "portfolio": {"type": "naive"},
        "execution": {"type": "immediate"},
    }

    with pytest.raises(ValueError, match="api source requires 'url'"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_supports_eastmoney_sse_ext_field_map_sources() -> None:
    cfg = {
        "name": "cfg-eastmoney-ext-field-map",
        "data_feed": {
            "type": "eastmoney_sse_ext",
            "symbol": "600000",
            "sources": [
                {
                    "type": "sse",
                    "sse_url": "https://example.com/sse",
                    "field_map": {
                        "price": ["content.f2", "content.price"],
                        "volume": "content.f5",
                        "amount": "content.f6",
                    },
                },
                {
                    "type": "snapshot_api",
                    "snapshot_url": "https://example.com/snapshot",
                    "field_map": {
                        "price": "data.f43",
                        "price_scale": 100,
                        "volume": "data.f47",
                        "amount": "data.f48",
                    },
                },
            ],
        },
        "strategies": [
            {
                "type": "moving_average",
                "symbol": "600000",
                "short_window": 1,
                "long_window": 2,
            }
        ],
        "portfolio": {"type": "naive", "lot_size": 100, "initial_cash": 10_000},
        "execution": {"type": "immediate", "slippage": 0.0, "commission": 0.0},
        "risk": [{"type": "max_position", "limit": 200}],
        "reporters": [{"type": "equity"}],
    }

    engine = load_engine_from_dict(cfg)
    assert isinstance(engine.data_feed, EastmoneySSEExtendedFeed)


def test_load_engine_from_dict_rejects_invalid_snapshot_params_shape() -> None:
    cfg = {
        "name": "cfg-eastmoney-invalid",
        "data_feed": {
            "type": "eastmoney_sse_ext",
            "symbol": "600000",
            "snapshot_params": "bad",
        },
        "strategies": [
            {
                "type": "moving_average",
                "symbol": "600000",
                "short_window": 1,
                "long_window": 2,
            }
        ],
        "portfolio": {"type": "naive", "lot_size": 100, "initial_cash": 10_000},
        "execution": {"type": "immediate", "slippage": 0.0, "commission": 0.0},
        "reporters": [{"type": "equity"}],
    }

    with pytest.raises(ValueError, match="snapshot_params"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_rejects_invalid_eastmoney_sources_shape() -> None:
    cfg = {
        "name": "cfg-eastmoney-invalid-sources",
        "data_feed": {
            "type": "eastmoney_sse_ext",
            "symbol": "600000",
            "sources": "bad",
        },
        "strategies": [
            {
                "type": "moving_average",
                "symbol": "600000",
                "short_window": 1,
                "long_window": 2,
            }
        ],
        "portfolio": {"type": "naive", "lot_size": 100, "initial_cash": 10_000},
        "execution": {"type": "immediate", "slippage": 0.0, "commission": 0.0},
        "reporters": [{"type": "equity"}],
    }

    with pytest.raises(ValueError, match="data_feed.sources"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_ignores_disabled_strategies(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    cfg = {
        "name": "cfg-disabled-strategy",
        "data_feed": {"type": "local_csv", "path": str(csv_path), "symbol": "AAA"},
        "strategies": [
            {
                "type": "moving_average",
                # Missing symbol on purpose. Disabled strategies should be ignored.
                "enabled": False,
            },
            {
                "type": "uptrend",
                "symbol": "AAA",
                "window": 2,
                "enabled": True,
            },
        ],
        "portfolio": {"type": "naive", "lot_size": 100, "initial_cash": 10_000},
        "execution": {"type": "immediate", "slippage": 0.0, "commission": 0.0},
        "reporters": [{"type": "equity"}],
    }

    engine = load_engine_from_dict(cfg)
    assert len(engine.strategies) == 1
