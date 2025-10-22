from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Tuple

from .trades import Trade


def period_returns(equity_curve: List[Tuple[str, float]], period: str = "M") -> Dict[str, float]:
    """Compute period returns from equity curve.

    period: 'M' (YYYY-MM) or 'Y' (YYYY)
    Returns mapping period -> return (fraction)
    """
    buckets: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    for dt_iso, eq in equity_curve:
        try:
            dt = datetime.fromisoformat(dt_iso)
        except Exception:
            continue
        key = f"{dt.year:04d}-{dt.month:02d}" if period == "M" else f"{dt.year:04d}"
        buckets[key].append((dt_iso, eq))
    out: Dict[str, float] = {}
    for k, rows in buckets.items():
        rows.sort(key=lambda x: x[0])
        if len(rows) >= 2 and rows[0][1] > 0:
            out[k] = rows[-1][1] / rows[0][1] - 1.0
        else:
            out[k] = 0.0
    return dict(sorted(out.items()))


def trade_stats(trades: List[Trade]) -> Dict[str, float]:
    n = len(trades)
    if n == 0:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "avg_ret": 0.0,
            "avg_hold_days": 0.0,
        }
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl < 0]
    sum_win = sum(t.pnl for t in wins) if wins else 0.0
    sum_loss = -sum(t.pnl for t in losses) if losses else 0.0
    return {
        "trades": float(n),
        "win_rate": (len(wins) / n) if n else 0.0,
        "avg_win": (sum_win / len(wins)) if wins else 0.0,
        "avg_loss": -(sum_loss / len(losses)) if losses else 0.0,
        "profit_factor": (sum_win / sum_loss) if sum_loss > 0 else 0.0,
        "avg_ret": sum(t.ret for t in trades) / n,
        "avg_hold_days": sum(t.holding_days for t in trades) / n,
    }

