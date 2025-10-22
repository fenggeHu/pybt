
from typing import Iterable, List, Tuple
import math
import statistics as stats


def equity_to_returns(equity_curve: List[Tuple[str, float]]) -> List[float]:
    rets: List[float] = []
    prev = None
    for _, eq in equity_curve:
        if prev is None:
            prev = eq
            continue
        if prev <= 0:
            rets.append(0.0)
        else:
            rets.append((eq - prev) / prev)
        prev = eq
    return rets


def sharpe_ratio(rets: Iterable[float], risk_free_daily: float = 0.0) -> float:
    xs = [r - risk_free_daily for r in rets]
    if len(xs) < 2:
        return 0.0
    m = stats.mean(xs)
    sd = stats.stdev(xs)
    if sd == 0.0:
        return 0.0
    return m / sd * math.sqrt(252.0)


def max_drawdown(equity_curve: List[Tuple[str, float]]) -> float:
    peak = -math.inf
    mdd = 0.0
    for _, eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = 0.0 if peak <= 0 else (eq - peak) / peak
        mdd = min(mdd, dd)
    return mdd
