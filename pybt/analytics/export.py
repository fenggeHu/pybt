import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple

from .trades import Trade


def export_equity_csv(path: str, equity_curve: List[Tuple[str, float]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(["dt", "equity"])
        for dt, eq in equity_curve:
            w.writerow([dt, f"{eq:.6f}"])


def export_trades_csv(path: str, trades: List[Trade]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(["symbol", "side", "qty", "entry_dt", "entry_px", "exit_dt", "exit_px", "pnl", "ret", "holding_days"])
        for t in trades:
            w.writerow([t.symbol, t.side, t.qty, t.entry_dt, f"{t.entry_px:.6f}", t.exit_dt, f"{t.exit_px:.6f}", f"{t.pnl:.6f}", f"{t.ret:.6f}",
                        t.holding_days])


def export_metrics_json(path: str, metrics: Dict[str, float]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w') as f:
        json.dump(metrics, f, indent=2, sort_keys=True)
