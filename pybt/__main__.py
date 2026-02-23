"""CLI entrypoint for running PyBT backtests from JSON config.

Usage:
    python -m pybt --config path/to/config.json [--log-level INFO] [--json-logs]
"""

import argparse
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping, Optional

from pybt import configure_logging
from pybt.configuration import load_config_dict, load_engine_from_dict


try:
    _PYBT_VERSION = version("pybt")
except PackageNotFoundError:
    _PYBT_VERSION = "0.0.0"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pybt", description="Run PyBT backtest from config."
    )
    parser.add_argument(
        "--config", type=Path, required=True, help="Path to JSON config file"
    )
    parser.add_argument(
        "--log-level", default="INFO", help="Logging level (default: INFO)"
    )
    parser.add_argument("--json-logs", action="store_true", help="Emit JSON log lines")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate config and wiring, then exit without running backtest",
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Run a user-friendly self-check report and exit",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_PYBT_VERSION}",
    )
    args = parser.parse_args(argv)

    if args.validate and args.self_check:
        parser.error("--validate and --self-check cannot be used together")

    configure_logging(level=args.log_level, json_format=args.json_logs)
    try:
        cfg_path = args.config.resolve()
        raw_cfg = load_config_dict(cfg_path)
        engine = load_engine_from_dict(raw_cfg, config_base_dir=cfg_path.parent)
    except Exception as exc:
        print(f"[ERROR] Config check failed: {exc}", file=sys.stderr)
        print(
            "[HINT] Run `pybt --config <file> --self-check` after fixing params/plugins.",
            file=sys.stderr,
        )
        return 2

    if args.validate:
        print(f"[OK] Validation passed: {args.config}")
        return 0
    if args.self_check:
        print("\n".join(_build_self_check_report(cfg_path, raw_cfg)))
        return 0

    try:
        engine.run()
    except Exception as exc:
        print(f"[ERROR] Run failed: {exc}", file=sys.stderr)
        return 3
    return 0


def _is_enabled(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "off", "no"}
    return bool(value)


def _plugin_name(component: Any) -> str:
    if isinstance(component, Mapping):
        name = component.get("plugin")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return "-"


def _build_self_check_report(config_path: Path, raw_cfg: Mapping[str, Any]) -> list[str]:
    strategies = raw_cfg.get("strategies")
    strategy_items = strategies if isinstance(strategies, list) else []
    strategy_total = len(strategy_items)
    strategy_enabled = 0
    strategy_plugins: list[str] = []
    for one in strategy_items:
        if not isinstance(one, Mapping):
            continue
        if _is_enabled(one.get("enabled", True)):
            strategy_enabled += 1
        strategy_plugins.append(_plugin_name(one))
    if len(strategy_plugins) > 5:
        strategy_preview = ", ".join(strategy_plugins[:5]) + ", ..."
    else:
        strategy_preview = ", ".join(strategy_plugins) if strategy_plugins else "-"

    risk_items = raw_cfg.get("risk")
    risk_count = len(risk_items) if isinstance(risk_items, list) else 0
    reporter_items = raw_cfg.get("reporters")
    reporter_count = len(reporter_items) if isinstance(reporter_items, list) else 0

    return [
        f"[OK] Config loaded: {config_path}",
        f"[OK] Run name: {raw_cfg.get('name', '-')}",
        f"[OK] Data feed plugin: {_plugin_name(raw_cfg.get('data_feed'))}",
        "[OK] Strategies: "
        f"total={strategy_total}, enabled={strategy_enabled}, plugins={strategy_preview}",
        f"[OK] Portfolio plugin: {_plugin_name(raw_cfg.get('portfolio'))}",
        f"[OK] Execution plugin: {_plugin_name(raw_cfg.get('execution'))}",
        f"[OK] Optional blocks: risk={risk_count}, reporters={reporter_count}",
        "[OK] Self-check passed: config syntax, plugin loading, required params.",
    ]


if __name__ == "__main__":
    sys.exit(main())
