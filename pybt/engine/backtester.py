
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from pybt.data.bar import Bar
from pybt.execution.broker import SimBroker, Fill
from pybt.portfolio.portfolio import Portfolio
from pybt.risk.metrics import equity_to_returns, max_drawdown, sharpe_ratio
from pybt.strategy.base import Strategy
from pybt.analytics.trades import TradeLedger


@dataclass
class BacktestResult:
    equity_curve: List[tuple]
    metrics: Dict[str, float]
    fills: List[Fill]
    trades: List[dict]


def run_backtest(
    bars: List[Bar],
    strategy: Strategy,
    portfolio: Optional[Portfolio] = None,
    broker: Optional[SimBroker] = None,
) -> BacktestResult:
    portfolio = portfolio or Portfolio()
    broker = broker or SimBroker()
    fills: List[Fill] = []
    ledger = TradeLedger()

    # We will fill at bar.open; mark PnL at bar.close
    log = logging.getLogger(__name__)
    for bar in bars:
        sig = strategy.on_bar(bar)
        if sig is not None:
            if sig.target_units is None:
                raise ValueError("Weight-based signals require the multi-asset engine with an allocator")
            fill = broker.fill_to_target(bar, current_units=portfolio.units, target_units=sig.target_units)
            if fill is not None:
                # Tag single-asset symbol for analytics
                fill.symbol = fill.symbol or "ASSET"
                portfolio.on_fill(fill)
                fills.append(fill)
                ledger.on_fill(fill)
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f"Fill {fill.dt} qty={fill.qty} px={fill.price:.4f} comm={fill.commission:.4f}")
        portfolio.mark_to_market(bar)

    eq = portfolio.equity_curve
    rets = equity_to_returns(eq)
    total_return = 0.0 if not eq else (eq[-1][1] / eq[0][1] - 1.0)
    n = max(1, len(eq))
    cagr = (eq[-1][1] / eq[0][1]) ** (252.0 / n) - 1.0 if n > 1 else 0.0
    metrics = {
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe_ratio(rets),
        "max_drawdown": max_drawdown(eq),
    }
    # Convert trades to plain dicts for easy JSON export
    trades = [t.__dict__ for t in ledger.get_trades()]
    return BacktestResult(equity_curve=eq, metrics=metrics, fills=fills, trades=trades)
