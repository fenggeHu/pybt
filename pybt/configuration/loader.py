"""Config-driven engine builder with lightweight validation."""

import json
from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence, Union

from pybt.core.engine import BacktestEngine, EngineConfig
from pybt.core.interfaces import (
    DataFeed,
    ExecutionHandler,
    PerformanceReporter,
    Portfolio,
    RiskManager,
    Strategy,
)
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
    # User config is the supplier; this resolver owns validation and returns a concrete feed.
    feed_type = _require(cfg, "type")
    if feed_type in {"local_csv", "local_file"}:
        from pybt.data import LocalCSVBarFeed

        path = Path(_require(cfg, "path"))
        symbol = cfg.get("symbol")
        start = _parse_dt(cfg.get("start"))
        end = _parse_dt(cfg.get("end"))
        return LocalCSVBarFeed(path=path, symbol=symbol, start=start, end=end)

    if feed_type == "inmemory":
        from pybt.data import InMemoryBarFeed

        raw_bars = _require(cfg, "bars")
        bars: list[Bar] = []
        for raw in raw_bars:
            ts = _parse_dt(_require(raw, "timestamp"))
            if ts is None:
                raise ValueError("Bar.timestamp cannot be null")
            ts_dt: datetime = ts
            bars.append(
                Bar(
                    symbol=_require(raw, "symbol"),
                    timestamp=ts_dt,
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
        from pybt.data import RESTPollingFeed

        return RESTPollingFeed(
            symbol=_require(cfg, "symbol"),
            url=_require(cfg, "url"),
            poll_interval=float(cfg.get("poll_interval", 1.0)),
            max_ticks=cfg.get("max_ticks"),
        )

    if feed_type == "websocket":
        from pybt.data import WebSocketJSONFeed

        return WebSocketJSONFeed(
            symbol=_require(cfg, "symbol"),
            url=_require(cfg, "url"),
            max_ticks=cfg.get("max_ticks"),
            heartbeat_interval=cfg.get("heartbeat_interval"),
        )

    if feed_type == "adata":
        from pybt.data import ADataLiveFeed

        return ADataLiveFeed(
            symbol=_require(cfg, "symbol"),
            poll_interval=float(cfg.get("poll_interval", 1.0)),
            max_ticks=cfg.get("max_ticks"),
        )

    if feed_type == "eastmoney_sse":
        from pybt.data import EastmoneySSEFeed

        return EastmoneySSEFeed(
            symbol=_require(cfg, "symbol"),
            sse_url=cfg.get("sse_url"),
            secid=cfg.get("secid"),
            token=str(cfg.get("token", "")),
            cname=cfg.get("cname"),
            seq=int(cfg.get("seq", 0)),
            noop=int(cfg.get("noop", 0)),
            max_ticks=cfg.get("max_ticks"),
            max_reconnects=int(cfg.get("max_reconnects", 3)),
            backoff_seconds=float(cfg.get("backoff_seconds", 0.5)),
            connect_timeout=float(cfg.get("connect_timeout", 5.0)),
            read_timeout=float(cfg.get("read_timeout", 30.0)),
            snapshot_url=str(
                cfg.get("snapshot_url", "https://push2.eastmoney.com/api/qt/stock/get")
            ),
            snapshot_fields=str(cfg.get("snapshot_fields", "f43,f47,f48")),
            snapshot_ut=str(cfg.get("snapshot_ut", "fa5fd1943c7b386f172d6893dbfba10b")),
            price_scale=float(cfg.get("price_scale", 100.0)),
        )

    raise ValueError(f"Unsupported data_feed type: {feed_type}")


def _build_strategy(cfg: Mapping[str, Any]) -> Strategy:
    # Strategies are constructed from user-supplied settings; invalid types fail fast.
    strat_type = _require(cfg, "type")
    if strat_type == "moving_average":
        from pybt.strategies import MovingAverageCrossStrategy

        return MovingAverageCrossStrategy(
            symbol=_require(cfg, "symbol"),
            short_window=int(cfg.get("short_window", 5)),
            long_window=int(cfg.get("long_window", 20)),
            strategy_id=cfg.get("strategy_id", "mac"),
        )
    if strat_type == "uptrend":
        from pybt.strategies import UptrendBreakoutStrategy

        return UptrendBreakoutStrategy(
            symbol=_require(cfg, "symbol"),
            window=int(cfg.get("window", 20)),
            breakout_factor=float(cfg.get("breakout_factor", 1.5)),
            strategy_id=cfg.get("strategy_id", "uptrend"),
        )
    if strat_type == "plugin":
        class_path = _require(cfg, "class_path")
        if not isinstance(class_path, str) or "." not in class_path:
            raise ValueError(
                "Plugin strategy class_path must be in '<module>.<ClassName>' format"
            )

        module_name, _, class_name = class_path.rpartition(".")
        try:
            module = import_module(module_name)
            strategy_cls = getattr(module, class_name)
        except (ImportError, AttributeError) as exc:
            raise ValueError(
                f"Unable to resolve plugin strategy: {class_path}"
            ) from exc

        params = cfg.get("params", {})
        if not isinstance(params, Mapping):
            raise ValueError("Plugin strategy params must be an object")

        try:
            strategy = strategy_cls(**dict(params))
        except TypeError as exc:
            raise ValueError(
                f"Unable to initialize plugin strategy: {class_path}"
            ) from exc

        if not isinstance(strategy, Strategy):
            raise ValueError(f"Plugin strategy '{class_path}' must implement Strategy")
        return strategy
    raise ValueError(f"Unsupported strategy type: {strat_type}")


def _build_execution(cfg: Mapping[str, Any]) -> ExecutionHandler:
    from pybt.execution import ImmediateExecutionHandler

    exec_type = _require(cfg, "type")
    if exec_type != "immediate":
        raise ValueError(f"Unsupported execution type: {exec_type}")
    return ImmediateExecutionHandler(
        slippage=float(cfg.get("slippage", 0.0)),
        commission=float(cfg.get("commission", 0.0)),
        partial_fill_ratio=cfg.get("partial_fill_ratio"),
        max_staleness=cfg.get("max_staleness"),
        fill_timing=cfg.get("fill_timing", "current_close"),
    )


def _build_portfolio(cfg: Mapping[str, Any]) -> Portfolio:
    from pybt.portfolio import NaivePortfolio

    port_type = _require(cfg, "type")
    if port_type != "naive":
        raise ValueError(f"Unsupported portfolio type: {port_type}")
    return NaivePortfolio(
        lot_size=int(cfg.get("lot_size", 100)),
        initial_cash=float(cfg.get("initial_cash", 100_000.0)),
    )


def _build_risk_managers(
    cfgs: Optional[Sequence[Mapping[str, Any]]],
    *,
    default_initial_cash: float,
) -> list[RiskManager]:
    managers: list[RiskManager] = []
    for cfg in cfgs or []:
        risk_type = _require(cfg, "type")
        if risk_type == "max_position":
            from pybt.risk import MaxPositionRisk

            managers.append(MaxPositionRisk(limit=int(_require(cfg, "limit"))))
        elif risk_type == "buying_power":
            from pybt.risk import BuyingPowerRisk

            managers.append(
                BuyingPowerRisk(
                    initial_cash=float(cfg.get("initial_cash", default_initial_cash)),
                    max_leverage=float(cfg.get("max_leverage", 1.0)),
                    reserve_cash=float(cfg.get("reserve_cash", 0.0)),
                )
            )
        elif risk_type == "concentration":
            from pybt.risk import ConcentrationRisk

            managers.append(
                ConcentrationRisk(
                    initial_cash=float(cfg.get("initial_cash", default_initial_cash)),
                    max_fraction=float(cfg.get("max_fraction", 0.5)),
                )
            )
        elif risk_type == "price_band":
            from pybt.risk import PriceBandRisk

            managers.append(PriceBandRisk(band_pct=float(cfg.get("band_pct", 0.05))))
        else:
            raise ValueError(f"Unsupported risk manager type: {risk_type}")
    return managers


def _build_reporters(
    cfgs: Optional[Sequence[Mapping[str, Any]]],
    *,
    default_initial_cash: float,
) -> list[PerformanceReporter]:
    reporters: list[PerformanceReporter] = []
    for cfg in cfgs or []:
        rep_type = _require(cfg, "type")
        if rep_type == "equity":
            from pybt.analytics import EquityCurveReporter

            reporters.append(
                EquityCurveReporter(
                    initial_cash=float(cfg.get("initial_cash", default_initial_cash))
                )
            )
        elif rep_type == "detailed":
            from pybt.analytics import DetailedReporter

            reporters.append(
                DetailedReporter(
                    initial_cash=float(cfg.get("initial_cash", default_initial_cash)),
                    track_equity_curve=bool(cfg.get("track_equity_curve", True)),
                )
            )
        elif rep_type == "tradelog":
            from pybt.analytics import TradeLogReporter

            jsonl = cfg.get("jsonl_path")
            sqlite = cfg.get("sqlite_path")
            reporters.append(
                TradeLogReporter(
                    jsonl_path=Path(jsonl) if jsonl else None,
                    sqlite_path=Path(sqlite) if sqlite else None,
                )
            )
        else:
            raise ValueError(f"Unsupported reporter type: {rep_type}")
    return reporters


def load_engine_from_dict(raw: Mapping[str, Any]) -> BacktestEngine:
    """Load BacktestEngine from an in-memory config dict."""

    data_feed = _build_feed(_require(raw, "data_feed"))
    strategies_cfg = _require(raw, "strategies")
    if not isinstance(strategies_cfg, Iterable):
        raise ValueError("strategies must be an array")
    strategies = [_build_strategy(item) for item in strategies_cfg]

    portfolio_cfg = _require(raw, "portfolio")
    portfolio = _build_portfolio(portfolio_cfg)
    execution = _build_execution(_require(raw, "execution"))

    default_initial_cash = float(portfolio_cfg.get("initial_cash", 100_000.0))
    risk = _build_risk_managers(
        raw.get("risk"), default_initial_cash=default_initial_cash
    )
    reporters = _build_reporters(
        raw.get("reporters"), default_initial_cash=default_initial_cash
    )

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


def load_engine_from_json(path: Union[Path, str]) -> BacktestEngine:
    """Load BacktestEngine from a JSON config file with validation.

    The config file is the supplier; this builder owns validation and wiring,
    returning an engine that owns the lifecycle of all constructed components.
    """

    cfg_path = Path(path)
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    return load_engine_from_dict(raw)


__all__ = ["load_engine_from_dict", "load_engine_from_json"]
