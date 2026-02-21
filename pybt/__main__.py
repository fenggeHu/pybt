"""CLI entrypoint for running PyBT backtests from JSON config.

Usage:
    python -m pybt --config path/to/config.json [--log-level INFO] [--json-logs]
"""

import argparse
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional

from pybt import configure_logging, load_engine_from_json


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
        "--version",
        action="version",
        version=f"%(prog)s {_PYBT_VERSION}",
    )
    args = parser.parse_args(argv)

    configure_logging(level=args.log_level, json_format=args.json_logs)
    engine = load_engine_from_json(args.config)
    if args.validate:
        return 0
    engine.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
