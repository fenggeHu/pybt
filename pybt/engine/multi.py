from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

from pybt.data.bar import Bar
from pybt.data.feed import DataFeed
from pybt.execution.broker import SimBroker, Fill
from pybt.execution.order import Order
from pybt.portfolio.multi import MultiPortfolio
from pybt.risk.metrics import equity_to_returns, max_drawdown, sharpe_ratio
from pybt.risk.rules import RiskConfig, RiskManager
from pybt.strategy.base import Strategy, Signal
from pybt.analytics.trades import TradeLedger
from pybt.allocation.weights import WeightAllocator


@dataclass
class BacktestResult:
    equity_curve: List[tuple]
    metrics: Dict[str, float]
    fills: List[Fill]
    trades: List[dict]


def _signal_to_order(symbol: str, current_units: int, sig: Signal) -> Optional[Order]:
    target = int(sig.target_units)
    delta = target - current_units
    if delta == 0:
        return None
    return Order(symbol=symbol, qty=delta, type="MARKET", tag="to_target")


def run_backtest_multi(
    data_by_symbol: Dict[str, List[Bar]],
    strategies: Dict[str, Strategy],
    portfolio: Optional[MultiPortfolio] = None,
    broker: Optional[SimBroker] = None,
    risk: Optional[RiskManager] = None,
    allocator: Optional[WeightAllocator] = None,
) -> BacktestResult:
    portfolio = portfolio or MultiPortfolio()
    broker = broker or SimBroker()
    risk = risk or RiskManager(RiskConfig())
    fills: List[Fill] = []
    ledger = TradeLedger()

    feed = DataFeed(data_by_symbol)
    last_close: Dict[str, float] = {}

    log = logging.getLogger(__name__)
    for evt in feed:
        dt_iso = evt.dt_iso
        # 1) Gather strategy intents per symbol
        desired_targets: Dict[str, int] = {}
        weight_targets: Dict[str, float] = {}
        symbol_orders: Dict[str, List[Order]] = {}
        for sym, bar in evt.items:
            last_close[sym] = bar.close
            strat = strategies.get(sym)
            if strat is None:
                continue
            # Optional sync of current position into strategy
            if hasattr(strat, 'sync_position'):
                try:
                    strat.sync_position(portfolio.position(sym))  # type: ignore[attr-defined]
                except Exception:
                    pass
            out = strat.on_bar(bar)
            if out is None:
                continue
            if hasattr(out, 'target_units'):
                if out.target_units is not None:
                    desired_targets[sym] = int(out.target_units)
                elif out.target_weight is not None:
                    weight_targets[sym] = float(out.target_weight)
            elif isinstance(out, list):
                # list[Order] path (optional if user strategies implement it)
                symbol_orders[sym] = [o for o in out if isinstance(o, Order)]

        if weight_targets:
            if allocator is not None:
                equity = portfolio.total_equity(last_close)
                weight_units = allocator.weights_to_units(weight_targets, equity=equity, prices=last_close)
                for sym, units in weight_units.items():
                    desired_targets[sym] = units
            else:
                log.warning("Weight signals received but no allocator provided; ignoring weights.")

        # 2) Risk: clamp targets
        if desired_targets:
            desired_targets = risk.clamp_target_units(desired_targets)
            # Convert to orders against current positions
            for sym, tgt in desired_targets.items():
                cur = portfolio.position(sym)
                od = _signal_to_order(sym, cur, Signal(target_units=tgt))
                if od is not None:
                    symbol_orders.setdefault(sym, []).append(od)

        # 3) Protective stops
        stop_orders = risk.protective_stop_orders(portfolio, last_close)
        for od in stop_orders:
            symbol_orders.setdefault(od.symbol, []).append(od)

        # 4) Execute orders for symbols present today
        for sym, bar in evt.items:
            orders = symbol_orders.get(sym, [])
            if not orders:
                continue
            # Convert dataclass to simple dicts for broker
            dicts = [o.to_dict() for o in orders]
            got = broker.process_orders(sym, bar, portfolio.position(sym), dicts)
            for f in got:
                portfolio.on_fill(f)
                fills.append(f)
                ledger.on_fill(f)
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f"Fill {sym} {f.dt} qty={f.qty} px={f.price:.4f} comm={f.commission:.4f}")

        # 5) Mark-to-market
        portfolio.mark_to_market(dt_iso, last_close)

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
    trades = [t.__dict__ for t in ledger.get_trades()]
    return BacktestResult(equity_curve=eq, metrics=metrics, fills=fills, trades=trades)
