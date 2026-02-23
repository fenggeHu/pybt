from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _plugin_registry_path() -> str:
    return str(Path(__file__).resolve().parent.parent / "plugins" / "plugin.jsonc")


def _config(csv_path: Path) -> dict:
    return {
        "name": "cli-demo",
        "plugin_registry": _plugin_registry_path(),
        "data_feed": {
            "plugin": "local_csv_feed",
            "params": {"path": str(csv_path), "symbol": "AAA"},
        },
        "strategies": [
            {
                "plugin": "moving_average",
                "params": {
                    "symbol": "AAA",
                    "short_window": 1,
                    "long_window": 2,
                },
            }
        ],
        "portfolio": {
            "plugin": "naive_portfolio",
            "params": {"lot_size": 100, "initial_cash": 10_000},
        },
        "execution": {
            "plugin": "immediate_execution",
            "params": {"slippage": 0.0, "commission": 0.0},
        },
        "risk": [{"plugin": "max_position_risk", "params": {"limit": 200}}],
        "reporters": [{"plugin": "equity_reporter", "params": {"initial_cash": 10_000}}],
    }


def test_cli_runs_with_config(tmp_path: Path) -> None:
    csv_path = tmp_path / "AAA" / "Bar.csv"
    csv_path.parent.mkdir(parents=True)
    csv_path.write_text(
        """date,open,high,low,close,volume,amount
2024-01-01,10,11,9,10.5,1000,10000
2024-01-02,10.5,11.5,10,11,1200,13200
""",
        encoding="utf-8",
    )

    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(_config(csv_path)), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pybt",
            "--config",
            str(cfg_path),
            "--log-level",
            "WARNING",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    assert result.returncode == 0, result.stderr


def test_cli_validate_only(tmp_path: Path) -> None:
    csv_path = tmp_path / "AAA" / "Bar.csv"
    csv_path.parent.mkdir(parents=True)
    csv_path.write_text(
        """date,open,high,low,close,volume,amount
2024-01-01,10,11,9,10.5,1000,10000
""",
        encoding="utf-8",
    )

    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(_config(csv_path)), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "pybt", "--config", str(cfg_path), "--validate"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    assert result.returncode == 0, result.stderr
    assert "[OK] Validation passed:" in result.stdout


def test_cli_self_check_prints_summary(tmp_path: Path) -> None:
    csv_path = tmp_path / "AAA" / "Bar.csv"
    csv_path.parent.mkdir(parents=True)
    csv_path.write_text(
        """date,open,high,low,close,volume,amount
2024-01-01,10,11,9,10.5,1000,10000
""",
        encoding="utf-8",
    )

    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(_config(csv_path)), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "pybt", "--config", str(cfg_path), "--self-check"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    assert result.returncode == 0, result.stderr
    assert "[OK] Self-check passed:" in result.stdout


def test_cli_version_flag() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pybt", "--version"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().startswith("pybt ")
