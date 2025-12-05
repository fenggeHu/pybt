"""Config-driven engine builder with lightweight validation.

JSON schema (example):

{
  "name": "demo",
  "data_feed": {"type": "local_csv", "path": "./data/AAA/Bar.csv", "symbol": "AAA"},
  "strategies": [{"type": "moving_average", "symbol": "AAA", "short_window": 5, "long_window": 20}],
  "portfolio": {"type": "naive", "lot_size": 100, "initial_cash": 100000},
  "execution": {"type": "immediate", "slippage": 0.01, "commission": 1.0},
  "risk": [{"type": "max_position", "limit": 500}],
  "reporters": [{"type": "equity", "initial_cash": 100000}]
}
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

from pybt.analytics import DetailedReporter, EquityCurveReporter
from pybt.core.engine import BacktestEngine, EngineConfig
from pybt.core.interfaces import DataFeed, PerformanceReporter, RiskManager, Strategy
from pybt.data import InMemoryBarFeed, LocalCSVBarFeed, RESTPollingFeed, WebSocketJSONFeed, load_bars_from_csv
from pybt.execution import ImmediateExecutionHandler
from pybt.portfolio import NaivePortfolio
from pybt.risk import MaxPositionRisk
from pybt.strategies import MovingAverageCrossStrategy, UptrendBreakoutStrategy
from pybt.core.models import Bar


def _require(mapping: Mapping[str, Any], key: str) -> Any:
    if key not in mapping:
        raise ValueError(f"Missing required config key: '{key}'")
    return mapping[key]


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid datetime format: {value}") from exc


def _build_feed(cfg: Mapping[str, Any]) -> DataFeed:
    feed_type = _require(cfg, "type")
    if feed_type in {"local_csv", "local_file"}:
        path = Path(_require(cfg, "path"))
        symbol = cfg.get("symbol")
        start = _parse_dt(cfg.get("start"))
        end = _parse_dt(cfg.get("end"))
        return LocalCSVBarFeed(path=path, symbol=symbol, start=start, end=end)

    if feed_type == "inmemory":
        raw_bars = _require(cfg, "bars")
        bars: list[Bar] = []
        for raw in raw_bars:
            ts = _parse_dt(_require(raw, "timestamp"))
            bars.append(
                Bar(
                    symbol=_require(raw, "symbol"),
                    timestamp=ts,
                    open=float(_require(raw, "open")),
                    high=float(_require(raw, "high")),
                    low=float(_require(raw, "low")),
                    close=float(_require(raw, "close")),
                    volume=float(raw.get("volume", 0.0)),
                    amount=float(raw.get("amount", 0.0)),
                )
            )
        return InMemoryBarFeed(bars)

    if feed_type == "rest":
        return RESTPollingFeed(
            symbol=_require(cfg, "symbol"),
            url=_require(cfg, "url"),
            poll_interval=float(cfg.get("poll_interval", 1.0)),
            max_ticks=cfg.get("max_ticks"),
        )

    if feed_type == "websocket":
        return WebSocketJSONFeed(
            symbol=_require(cfg, "symbol"),
            url=_require(cfg, "url"),
            max_ticks=cfg.get("max_ticks"),
        )

    raise ValueError(f"Unsupported data_feed type: {feed_type}")


def _build_strategy(cfg: Mapping[str, Any]) -> Strategy:
    strat_type = _require(cfg, "type")
    if strat_type == "moving_average":
        return MovingAverageCrossStrategy(
            symbol=_require(cfg, "symbol"),
            short_window=int(_require(cfg, "short_window")),
            long_window=int(_require(cfg, "long_window")),
            strategy_id=cfg.get("strategy_id", "mac"),
        )
    if strat_type == "uptrend":
        return UptrendBreakoutStrategy(
            symbol=_require(cfg, "symbol"),
            window=int(cfg.get("window", 20)),
            breakout_factor=float(cfg.get("breakout_factor", 1.5)),
            strategy_id=cfg.get("strategy_id", "uptrend"),
        )
    raise ValueError(f"Unsupported strategy type: {strat_type}")


def _build_execution(cfg: Mapping[str, Any]) -> ImmediateExecutionHandler:
    exec_type = _require(cfg, "type")
    if exec_type != "immediate":
        raise ValueError(f"Unsupported execution type: {exec_type}")
    return ImmediateExecutionHandler(
        slippage=float(cfg.get("slippage", 0.0)),
        commission=float(cfg.get("commission", 0.0)),
    )


def _build_portfolio(cfg: Mapping[str, Any]) -> NaivePortfolio:
    port_type = _require(cfg, "type")
    if port_type != "naive":
        raise ValueError(f"Unsupported portfolio type: {port_type}")
    return NaivePortfolio(
        lot_size=int(cfg.get("lot_size", 100)),
        initial_cash=float(cfg.get("initial_cash", 100_000.0)),
    )


def _build_risk_managers(cfgs: Optional[Sequence[Mapping[str, Any]]]) -> list[RiskManager]:
    managers: list[RiskManager] = []
    for cfg in cfgs or []:
        risk_type = _require(cfg, "type")
        if risk_type == "max_position":
            managers.append(MaxPositionRisk(limit=int(_require(cfg, "limit"))))
        else:
            raise ValueError(f"Unsupported risk manager type: {risk_type}")
    return managers


def _build_reporters(cfgs: Optional[Sequence[Mapping[str, Any]]]) -> list[PerformanceReporter]:
    reporters: list[PerformanceReporter] = []
    for cfg in cfgs or []:
        rep_type = _require(cfg, "type")
        if rep_type == "equity":
            reporters.append(EquityCurveReporter(initial_cash=float(cfg.get("initial_cash", 100_000.0))))
        elif rep_type == "detailed":
            reporters.append(
                DetailedReporter(
                    initial_cash=float(cfg.get("initial_cash", 100_000.0)),
                    track_equity_curve=bool(cfg.get("track_equity_curve", True)),
                )
            )
        else:
            raise ValueError(f"Unsupported reporter type: {rep_type}")
    return reporters


def load_engine_from_json(path: Path | str) -> BacktestEngine:
    """Load BacktestEngine from a JSON config file with validation."""

    cfg_path = Path(path)
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))

    data_feed = _build_feed(_require(raw, "data_feed"))
    strategies_cfg = _require(raw, "strategies")
    if not isinstance(strategies_cfg, Iterable):
        raise ValueError("strategies must be an array")
    strategies = [_build_strategy(item) for item in strategies_cfg]

    portfolio = _build_portfolio(_require(raw, "portfolio"))
    execution = _build_execution(_require(raw, "execution"))
    risk = _build_risk_managers(raw.get("risk"))
    reporters = _build_reporters(raw.get("reporters"))

    engine_cfg = EngineConfig(
        name=str(raw.get("name", "backtest")),
        start=_parse_dt(raw.get("start")),
        end=_parse_dt(raw.get("end")),
    )

    return BacktestEngine(
        data_feed=data_feed,
        strategies=strategies,
        portfolio=portfolio,
        execution=execution,
        risk_managers=risk,
        reporters=reporters,
        config=engine_cfg,
    )


__all__ = ["load_engine_from_json"]
