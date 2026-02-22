"""Config-driven engine builder with lightweight validation."""

from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

from .config_file import load_config_dict
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


def _as_object(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _as_object_array(value: Any, *, field_name: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be an array")
    items: list[Mapping[str, Any]] = []
    for idx, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name}[{idx}] must be an object")
        items.append(item)
    return items


def _as_str_mapping(
    value: Any, *, field_name: str, default: Optional[dict[str, str]] = None
) -> dict[str, str]:
    if value is None:
        return dict(default or {})
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    out = dict(default or {})
    for key, one in value.items():
        out[str(key)] = str(one)
    return out


def _is_enabled(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "off", "no"}
    return bool(value)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid datetime format: {value}") from exc


def _parse_request_timeout(cfg: Mapping[str, Any]) -> float | tuple[float, float]:
    connect_timeout = cfg.get("connect_timeout")
    read_timeout = cfg.get("read_timeout")
    if connect_timeout is not None or read_timeout is not None:
        return (
            float(connect_timeout if connect_timeout is not None else 5.0),
            float(read_timeout if read_timeout is not None else 5.0),
        )

    timeout = cfg.get("request_timeout", 5.0)
    if isinstance(timeout, (int, float)):
        return float(timeout)
    if isinstance(timeout, Mapping):
        connect = timeout.get("connect", timeout.get("connect_timeout", 5.0))
        read = timeout.get("read", timeout.get("read_timeout", 5.0))
        return (float(connect), float(read))
    if isinstance(timeout, Sequence) and not isinstance(
        timeout, (str, bytes, bytearray)
    ):
        values = list(timeout)
        if len(values) != 2:
            raise ValueError("data_feed.request_timeout array must contain 2 numbers")
        return (float(values[0]), float(values[1]))
    raise ValueError(
        "data_feed.request_timeout must be number, [connect,read], or object"
    )


def _build_simple_market_sources(
    cfg: Mapping[str, Any],
) -> Optional[list[Mapping[str, Any]]]:
    source = cfg.get("source")
    if source is None:
        return None
    if cfg.get("sources") is not None:
        raise ValueError(
            "data_feed.source cannot be used together with data_feed.sources"
        )

    source_type = str(source).strip().lower()
    if source_type not in {"sse", "api", "snapshot_api", "snapshot", "websocket"}:
        raise ValueError(
            "data_feed.source must be one of sse/api/snapshot_api/snapshot/websocket"
        )

    headers = _as_str_mapping(cfg.get("headers"), field_name="data_feed.headers")
    field_map = cfg.get("field_map")
    if field_map is not None and not isinstance(field_map, Mapping):
        raise ValueError("data_feed.field_map must be an object")
    params = cfg.get("params")
    if params is not None and not isinstance(params, Mapping):
        raise ValueError("data_feed.params must be an object")

    source_cfg: dict[str, Any] = {"type": source_type}
    if headers:
        source_cfg["headers"] = headers
    if field_map is not None:
        source_cfg["field_map"] = dict(field_map)
    if params is not None:
        source_cfg["params"] = dict(params)

    url = cfg.get("url")
    if url is not None:
        if not isinstance(url, str) or not url:
            raise ValueError("data_feed.url must be a non-empty string")
        if source_type == "sse":
            source_cfg["sse_url"] = url
        elif source_type == "api":
            source_cfg["url"] = url
        elif source_type in {"snapshot_api", "snapshot"}:
            source_cfg["snapshot_url"] = url
        else:
            source_cfg["url"] = url
    elif source_type == "websocket":
        raise ValueError("data_feed.url is required when data_feed.source=websocket")

    if source_type in {"snapshot_api", "snapshot"} and "on_demand_only" in cfg:
        source_cfg["on_demand_only"] = bool(cfg.get("on_demand_only"))
    if source_type == "api":
        for key in (
            "response_mode",
            "symbol_param",
            "symbol_template",
            "symbol_transform",
            "encoding",
            "on_demand_only",
        ):
            value = cfg.get(key)
            if value is not None:
                source_cfg[key] = value

    sources: list[Mapping[str, Any]] = [source_cfg]

    if source_type != "sse" or not _is_enabled(cfg.get("snapshot_fallback", True)):
        return sources

    snapshot_cfg: dict[str, Any] = {"type": "snapshot_api", "on_demand_only": True}
    snapshot_headers = _as_str_mapping(
        cfg.get("snapshot_headers"), field_name="data_feed.snapshot_headers"
    )
    if snapshot_headers:
        snapshot_cfg["headers"] = snapshot_headers
    snapshot_field_map = cfg.get("snapshot_field_map")
    if snapshot_field_map is not None:
        if not isinstance(snapshot_field_map, Mapping):
            raise ValueError("data_feed.snapshot_field_map must be an object")
        snapshot_cfg["field_map"] = dict(snapshot_field_map)
    snapshot_url = cfg.get("snapshot_url")
    if snapshot_url is not None:
        if not isinstance(snapshot_url, str) or not snapshot_url:
            raise ValueError("data_feed.snapshot_url must be a non-empty string")
        snapshot_cfg["snapshot_url"] = snapshot_url
    snapshot_params = cfg.get("snapshot_params")
    if snapshot_params is not None:
        if not isinstance(snapshot_params, Mapping):
            raise ValueError("data_feed.snapshot_params must be an object")
        snapshot_cfg["params"] = dict(snapshot_params)
    sources.append(snapshot_cfg)
    return sources


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

        raw_bars = _as_object_array(_require(cfg, "bars"), field_name="data_feed.bars")
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
            max_retries=int(cfg.get("max_retries", 3)),
            backoff_seconds=float(cfg.get("backoff_seconds", 0.5)),
            request_timeout=_parse_request_timeout(cfg),
        )

    if feed_type == "websocket":
        from pybt.data import WebSocketJSONFeed

        return WebSocketJSONFeed(
            symbol=_require(cfg, "symbol"),
            url=_require(cfg, "url"),
            max_ticks=cfg.get("max_ticks"),
            max_reconnects=int(cfg.get("max_reconnects", 3)),
            backoff_seconds=float(cfg.get("backoff_seconds", 0.5)),
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

        sse_headers = _as_str_mapping(
            cfg.get("sse_headers"), field_name="data_feed.sse_headers"
        )
        snapshot_headers = _as_str_mapping(
            cfg.get("snapshot_headers"), field_name="data_feed.snapshot_headers"
        )
        snapshot_params = cfg.get("snapshot_params")
        if snapshot_params is not None and not isinstance(snapshot_params, Mapping):
            raise ValueError("data_feed.snapshot_params must be an object")
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
            sse_base_url=str(
                cfg.get("sse_base_url", "https://92.newspush.eastmoney.com/sse")
            ),
            sse_headers=sse_headers,
            snapshot_url=str(
                cfg.get("snapshot_url", "https://push2.eastmoney.com/api/qt/stock/get")
            ),
            snapshot_fields=str(cfg.get("snapshot_fields", "f43,f47,f48")),
            snapshot_ut=str(cfg.get("snapshot_ut", "fa5fd1943c7b386f172d6893dbfba10b")),
            snapshot_headers=snapshot_headers,
            snapshot_params=dict(snapshot_params or {}),
            price_scale=float(cfg.get("price_scale", 100.0)),
        )
    if feed_type in {"eastmoney_sse_ext", "market_feed"}:
        from pybt.data import ComposableQuoteFeed

        reconnect_every_ticks = cfg.get("reconnect_every_ticks")
        heartbeat_timeout = cfg.get("heartbeat_timeout")
        sources = _build_simple_market_sources(cfg)
        if sources is None:
            sources_cfg = cfg.get("sources")
            sources = (
                _as_object_array(sources_cfg, field_name="data_feed.sources")
                if sources_cfg is not None
                else None
            )
        sse_headers = _as_str_mapping(
            cfg.get("sse_headers"), field_name="data_feed.sse_headers"
        )
        snapshot_headers = _as_str_mapping(
            cfg.get("snapshot_headers"), field_name="data_feed.snapshot_headers"
        )
        snapshot_params = cfg.get("snapshot_params")
        if snapshot_params is not None and not isinstance(snapshot_params, Mapping):
            raise ValueError("data_feed.snapshot_params must be an object")
        return ComposableQuoteFeed(
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
            sse_base_url=str(
                cfg.get("sse_base_url", "https://92.newspush.eastmoney.com/sse")
            ),
            sse_headers=sse_headers,
            snapshot_url=str(
                cfg.get("snapshot_url", "https://push2.eastmoney.com/api/qt/stock/get")
            ),
            snapshot_fields=str(cfg.get("snapshot_fields", "f43,f47,f48")),
            snapshot_ut=str(cfg.get("snapshot_ut", "fa5fd1943c7b386f172d6893dbfba10b")),
            snapshot_headers=snapshot_headers,
            snapshot_params=dict(snapshot_params or {}),
            price_scale=float(cfg.get("price_scale", 100.0)),
            reconnect_every_ticks=(
                int(reconnect_every_ticks)
                if reconnect_every_ticks is not None
                else None
            ),
            heartbeat_timeout=(
                float(heartbeat_timeout) if heartbeat_timeout is not None else None
            ),
            sources=sources,
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

    data_feed = _build_feed(
        _as_object(_require(raw, "data_feed"), field_name="data_feed")
    )
    strategies_cfg = _as_object_array(
        _require(raw, "strategies"), field_name="strategies"
    )
    enabled_strategies = [
        item for item in strategies_cfg if _is_enabled(item.get("enabled", True))
    ]
    strategies = [_build_strategy(item) for item in enabled_strategies]

    portfolio_cfg = _as_object(_require(raw, "portfolio"), field_name="portfolio")
    portfolio = _build_portfolio(portfolio_cfg)
    execution = _build_execution(
        _as_object(_require(raw, "execution"), field_name="execution")
    )

    default_initial_cash = float(portfolio_cfg.get("initial_cash", 100_000.0))
    risk_cfg = raw.get("risk")
    if risk_cfg is not None:
        risk_items = _as_object_array(risk_cfg, field_name="risk")
    else:
        risk_items = None
    risk = _build_risk_managers(risk_items, default_initial_cash=default_initial_cash)
    reporters_cfg = raw.get("reporters")
    if reporters_cfg is not None:
        reporter_items = _as_object_array(reporters_cfg, field_name="reporters")
    else:
        reporter_items = None
    reporters = _build_reporters(
        reporter_items, default_initial_cash=default_initial_cash
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
    """Load BacktestEngine from a JSON/JSONC config file with validation.

    The config file is the supplier; this builder owns validation and wiring,
    returning an engine that owns the lifecycle of all constructed components.
    """

    raw = load_config_dict(path)
    return load_engine_from_dict(raw)


__all__ = ["load_engine_from_dict", "load_engine_from_json"]
