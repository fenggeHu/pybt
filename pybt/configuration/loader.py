"""Config-driven engine builder using plugin.jsonc registry."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union
from uuid import uuid4

from .config_file import load_config_dict, resolve_config_refs
from .plugins import PluginLoader, PluginRegistry, find_default_registry_path
from pybt.core.engine import BacktestEngine, EngineConfig


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
    out: list[Mapping[str, Any]] = []
    for idx, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name}[{idx}] must be an object")
        out.append(item)
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


def _resolve_registry_path(
    raw: Mapping[str, Any],
    *,
    config_base_dir: Optional[Path],
    explicit_registry_path: Optional[Union[str, Path]],
) -> Path:
    if explicit_registry_path is not None:
        return Path(explicit_registry_path).resolve()

    value = raw.get("plugin_registry")
    if value is None:
        return find_default_registry_path(search_from=config_base_dir)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("plugin_registry must be a non-empty string when provided")

    path = Path(value.strip())
    if path.is_absolute():
        return path.resolve()
    if config_base_dir is not None:
        return (config_base_dir / path).resolve()
    return path.resolve()


def _create_loader(
    raw: Mapping[str, Any],
    *,
    config_base_dir: Optional[Path],
    plugin_registry_path: Optional[Union[str, Path]],
) -> PluginLoader:
    registry_path = _resolve_registry_path(
        raw,
        config_base_dir=config_base_dir,
        explicit_registry_path=plugin_registry_path,
    )
    if not registry_path.exists():
        raise ValueError(f"Plugin registry file not found: {registry_path}")
    registry = PluginRegistry.from_file(registry_path)
    return PluginLoader(registry)


def load_engine_from_dict(
    raw: Mapping[str, Any],
    *,
    plugin_registry_path: Optional[Union[str, Path]] = None,
    config_base_dir: Optional[Path] = None,
) -> BacktestEngine:
    """Load BacktestEngine from an in-memory config dict."""

    resolved_raw = resolve_config_refs(raw, base_dir=config_base_dir)
    if not isinstance(resolved_raw, Mapping):
        raise ValueError("Config JSON must be an object")

    plugin_loader = _create_loader(
        resolved_raw,
        config_base_dir=config_base_dir,
        plugin_registry_path=plugin_registry_path,
    )
    run_id = str(resolved_raw.get("run_id", uuid4().hex))

    data_feed_cfg = _as_object(
        _require(resolved_raw, "data_feed"), field_name="data_feed"
    )
    data_feed = plugin_loader.create_component(
        slot="data_feed",
        kind="data_feed",
        component=data_feed_cfg,
        run_id=run_id,
        engine_config=resolved_raw,
    )

    strategies_cfg = _as_object_array(
        _require(resolved_raw, "strategies"), field_name="strategies"
    )
    strategies = []
    for idx, item in enumerate(strategies_cfg):
        if not _is_enabled(item.get("enabled", True)):
            continue
        strategies.append(
            plugin_loader.create_component(
                slot=f"strategies[{idx}]",
                kind="strategy",
                component=item,
                run_id=run_id,
                engine_config=resolved_raw,
            )
        )

    portfolio_cfg = _as_object(
        _require(resolved_raw, "portfolio"), field_name="portfolio"
    )
    portfolio = plugin_loader.create_component(
        slot="portfolio",
        kind="portfolio",
        component=portfolio_cfg,
        run_id=run_id,
        engine_config=resolved_raw,
    )

    execution_cfg = _as_object(
        _require(resolved_raw, "execution"), field_name="execution"
    )
    execution = plugin_loader.create_component(
        slot="execution",
        kind="execution",
        component=execution_cfg,
        run_id=run_id,
        engine_config=resolved_raw,
    )

    risk: list[Any] = []
    risk_cfg = resolved_raw.get("risk")
    if risk_cfg is not None:
        risk_items = _as_object_array(risk_cfg, field_name="risk")
        for idx, item in enumerate(risk_items):
            if not _is_enabled(item.get("enabled", True)):
                continue
            risk.append(
                plugin_loader.create_component(
                    slot=f"risk[{idx}]",
                    kind="risk",
                    component=item,
                    run_id=run_id,
                    engine_config=resolved_raw,
                )
            )

    reporters: list[Any] = []
    reporters_cfg = resolved_raw.get("reporters")
    if reporters_cfg is not None:
        reporter_items = _as_object_array(reporters_cfg, field_name="reporters")
        for idx, item in enumerate(reporter_items):
            if not _is_enabled(item.get("enabled", True)):
                continue
            reporters.append(
                plugin_loader.create_component(
                    slot=f"reporters[{idx}]",
                    kind="reporter",
                    component=item,
                    run_id=run_id,
                    engine_config=resolved_raw,
                )
            )

    engine_cfg = EngineConfig(
        name=str(resolved_raw.get("name", "backtest")),
        start=_parse_dt(resolved_raw.get("start")),
        end=_parse_dt(resolved_raw.get("end")),
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


def load_engine_from_json(
    path: Union[Path, str], *, plugin_registry_path: Optional[Union[str, Path]] = None
) -> BacktestEngine:
    """Load BacktestEngine from a JSON/JSONC config file."""

    cfg_path = Path(path).resolve()
    raw = load_config_dict(cfg_path)
    return load_engine_from_dict(
        raw,
        plugin_registry_path=plugin_registry_path,
        config_base_dir=cfg_path.parent,
    )


__all__ = ["load_engine_from_dict", "load_engine_from_json"]
