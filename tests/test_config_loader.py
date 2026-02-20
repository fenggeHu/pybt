from datetime import datetime
from pathlib import Path

import pytest

from pybt import load_engine_from_dict, load_engine_from_json
from pybt.data.rest_feed import EastmoneySSEFeed


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
