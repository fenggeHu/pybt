from __future__ import annotations

import json
from pathlib import Path

import pytest

from pybt import load_engine_from_dict


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


def _write_plugin_bundle(tmp_path: Path) -> Path:
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    (plugin_dir / "local_csv_feed.py").write_text(
        """
from pathlib import Path
from pybt.data import LocalCSVBarFeed

def create(params, ctx):
    return LocalCSVBarFeed(path=Path(params["path"]), symbol=params.get("symbol"))
""",
        encoding="utf-8",
    )
    (plugin_dir / "naive_portfolio.py").write_text(
        """
from pybt.portfolio import NaivePortfolio

def create(params, ctx):
    return NaivePortfolio(
        lot_size=int(params.get("lot_size", 100)),
        initial_cash=float(params.get("initial_cash", 10000)),
    )
""",
        encoding="utf-8",
    )
    (plugin_dir / "immediate_execution.py").write_text(
        """
from pybt.execution import ImmediateExecutionHandler

def create(params, ctx):
    return ImmediateExecutionHandler()
""",
        encoding="utf-8",
    )
    (plugin_dir / "equity_reporter.py").write_text(
        """
from pybt.analytics import EquityCurveReporter

def create(params, ctx):
    return EquityCurveReporter(initial_cash=float(params.get("initial_cash", 10000)))
""",
        encoding="utf-8",
    )
    (plugin_dir / "custom_strategy.py").write_text(
        """
from pybt.core.enums import SignalDirection
from pybt.core.events import MarketEvent, SignalEvent
from pybt.core.interfaces import Strategy

class CustomStrategy(Strategy):
    def __init__(self, symbol: str, strategy_id: str = "plugin") -> None:
        super().__init__()
        self.symbol = symbol
        self.strategy_id = strategy_id
        self._fired = False

    def on_start(self) -> None:
        self._fired = False

    def on_market(self, event: MarketEvent) -> None:
        if self._fired or event.symbol != self.symbol:
            return
        self._fired = True
        self.bus.publish(
            SignalEvent(
                timestamp=event.timestamp,
                strategy_id=self.strategy_id,
                symbol=self.symbol,
                direction=SignalDirection.LONG,
                strength=1.0,
            )
        )

def create(params, ctx):
    return CustomStrategy(
        symbol=str(params["symbol"]),
        strategy_id=str(params.get("strategy_id", "plugin")),
    )
""",
        encoding="utf-8",
    )
    (plugin_dir / "invalid_strategy.py").write_text(
        """
class NotAStrategy:
    pass

def create(params, ctx):
    return NotAStrategy()
""",
        encoding="utf-8",
    )

    registry = {
        "version": 1,
        "plugin_dir": ".",
        "plugins": [
            {"name": "local_csv_feed", "kind": "data_feed"},
            {"name": "naive_portfolio", "kind": "portfolio"},
            {"name": "immediate_execution", "kind": "execution"},
            {"name": "equity_reporter", "kind": "reporter"},
            {
                "name": "custom_strategy",
                "kind": "strategy",
                "strict_params": True,
                "params": [{"name": "symbol", "type": "str", "required": True}],
            },
            {"name": "invalid_strategy", "kind": "strategy"},
        ],
    }
    registry_path = plugin_dir / "plugin.jsonc"
    registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    return registry_path


def _base_config(csv_path: Path, registry_path: Path) -> dict:
    return {
        "name": "plugin-demo",
        "plugin_registry": str(registry_path),
        "data_feed": {
            "plugin": "local_csv_feed",
            "params": {"path": str(csv_path), "symbol": "AAA"},
        },
        "strategies": [
            {"plugin": "custom_strategy", "params": {"symbol": "AAA"}}
        ],
        "portfolio": {"plugin": "naive_portfolio"},
        "execution": {"plugin": "immediate_execution"},
        "reporters": [{"plugin": "equity_reporter"}],
    }


def test_load_engine_from_dict_supports_custom_strategy_plugin(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    registry_path = _write_plugin_bundle(tmp_path)
    cfg = _base_config(csv_path, registry_path)

    engine = load_engine_from_dict(cfg)
    assert engine.strategies[0].__class__.__name__ == "CustomStrategy"
    engine.run()


def test_load_engine_from_dict_rejects_non_strategy_plugin(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    registry_path = _write_plugin_bundle(tmp_path)
    cfg = _base_config(csv_path, registry_path)
    cfg["strategies"] = [{"plugin": "invalid_strategy", "params": {}}]

    with pytest.raises(ValueError, match="PLUGIN_INTERFACE_MISMATCH"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_rejects_invalid_plugin_name(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path)
    registry_path = _write_plugin_bundle(tmp_path)
    cfg = _base_config(csv_path, registry_path)
    cfg["strategies"] = [{"plugin": "missing_strategy", "params": {}}]

    with pytest.raises(ValueError, match="PLUGIN_NOT_FOUND"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_rejects_unknown_strict_plugin_param(
    tmp_path: Path,
) -> None:
    csv_path = _write_csv(tmp_path)
    registry_path = _write_plugin_bundle(tmp_path)
    cfg = _base_config(csv_path, registry_path)
    cfg["strategies"] = [
        {"plugin": "custom_strategy", "params": {"symbol": "AAA", "oops": 1}}
    ]

    with pytest.raises(ValueError, match="PLUGIN_INVALID_PARAMS"):
        load_engine_from_dict(cfg)
