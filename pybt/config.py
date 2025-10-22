
from dataclasses import dataclass
from pathlib import Path
import json


@dataclass
class BacktestConfig:
    initial_cash: float = 100_000.0
    slippage_bps: float = 1.0
    commission_per_share: float = 0.0


def load_config(path: str) -> dict:
    """Load JSON config and return as dict.

    Example JSON (keys match CLI args where possible):
    {
      "csv": "data/SPY_sample.csv",
      "fast": 10,
      "slow": 30,
      "allow_short": false,
      "cash": 100000,
      "slip_bps": 1.0,
      "comm": 0.0,
      "out_dir": "out"
    }
    """
    p = Path(path)
    with p.open('r') as f:
        return json.load(f)
