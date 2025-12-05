"""CLI entrypoint for running PyBT backtests from JSON config.

Usage:
    python -m pybt --config path/to/config.json [--log-level INFO] [--json-logs]
"""

import argparse
import sys
from pathlib import Path

from pybt import configure_logging, load_engine_from_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PyBT backtest from config.")
    parser.add_argument("--config", type=Path, required=True, help="Path to JSON config file")
    parser.add_argument("--log-level", default="INFO", help="Logging level (default: INFO)")
    parser.add_argument("--json-logs", action="store_true", help="Emit JSON log lines")
    args = parser.parse_args(argv)

    configure_logging(level=args.log_level, json_format=args.json_logs)
    engine = load_engine_from_json(args.config)
    engine.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
