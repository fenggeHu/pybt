import json
import subprocess
import sys
from pathlib import Path


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

    cfg = {
        "name": "cli-demo",
        "data_feed": {"type": "local_csv", "path": str(csv_path), "symbol": "AAA"},
        "strategies": [{"type": "moving_average", "symbol": "AAA", "short_window": 1, "long_window": 2}],
        "portfolio": {"type": "naive", "lot_size": 100, "initial_cash": 10_000},
        "execution": {"type": "immediate", "slippage": 0.0, "commission": 0.0},
        "risk": [{"type": "max_position", "limit": 200}],
        "reporters": [{"type": "equity", "initial_cash": 10_000}],
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "pybt", "--config", str(cfg_path), "--log-level", "WARNING"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    assert result.returncode == 0, result.stderr
