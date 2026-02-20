import sys
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


def _base_config(csv_path: Path) -> dict:
    return {
        "name": "plugin-demo",
        "data_feed": {"type": "local_csv", "path": str(csv_path), "symbol": "AAA"},
        "portfolio": {"type": "naive", "lot_size": 100, "initial_cash": 10_000},
        "execution": {"type": "immediate", "slippage": 0.0, "commission": 0.0},
        "risk": [{"type": "max_position", "limit": 200}],
        "reporters": [{"type": "equity", "initial_cash": 10_000}],
    }


def _write_plugin_module(tmp_path: Path) -> str:
    module_name = "plugin_fixture"
    module_path = tmp_path / f"{module_name}.py"
    module_path.write_text(
        """
from pybt.core.enums import SignalDirection
from pybt.core.events import MarketEvent, SignalEvent
from pybt.core.interfaces import Strategy


class NoopPluginStrategy(Strategy):
    def __init__(self, symbol: str, strategy_id: str = "plugin-noop") -> None:
        super().__init__()
        self.symbol = symbol
        self.strategy_id = strategy_id
        self._emitted = False

    def on_start(self) -> None:
        self._emitted = False

    def on_market(self, event: MarketEvent) -> None:
        if self._emitted or event.symbol != self.symbol:
            return
        self._emitted = True
        self.bus.publish(
            SignalEvent(
                timestamp=event.timestamp,
                strategy_id=self.strategy_id,
                symbol=self.symbol,
                direction=SignalDirection.LONG,
                strength=1.0,
            )
        )


class NotAStrategy:
    pass
""",
        encoding="utf-8",
    )
    sys.modules.pop(module_name, None)
    return module_name


def test_load_engine_from_dict_supports_plugin_strategy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csv_path = _write_csv(tmp_path)
    module_name = _write_plugin_module(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    cfg = _base_config(csv_path)
    cfg["strategies"] = [
        {
            "type": "plugin",
            "class_path": f"{module_name}.NoopPluginStrategy",
            "params": {"symbol": "AAA", "strategy_id": "plugin"},
        }
    ]

    engine = load_engine_from_dict(cfg)
    assert engine.strategies[0].__class__.__name__ == "NoopPluginStrategy"
    engine.run()


def test_load_engine_from_dict_rejects_non_strategy_plugin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csv_path = _write_csv(tmp_path)
    module_name = _write_plugin_module(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    cfg = _base_config(csv_path)
    cfg["strategies"] = [
        {
            "type": "plugin",
            "class_path": f"{module_name}.NotAStrategy",
            "params": {},
        }
    ]

    with pytest.raises(ValueError, match="must implement Strategy"):
        load_engine_from_dict(cfg)


def test_load_engine_from_dict_rejects_invalid_plugin_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csv_path = _write_csv(tmp_path)
    module_name = _write_plugin_module(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    cfg = _base_config(csv_path)
    cfg["strategies"] = [
        {
            "type": "plugin",
            "class_path": f"{module_name}.MissingStrategy",
            "params": {},
        }
    ]

    with pytest.raises(ValueError, match="Unable to resolve plugin strategy"):
        load_engine_from_dict(cfg)
