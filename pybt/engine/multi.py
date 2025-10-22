import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from pybt.allocation.weights import WeightAllocator
from pybt.analytics.trades import TradeLedger
from pybt.data.bar import Bar
from pybt.data.feed import DataFeed
from pybt.execution.broker import SimBroker, Fill
from pybt.execution.order import Order
from pybt.portfolio.multi import MultiPortfolio
from pybt.risk.metrics import equity_to_returns, max_drawdown, sharpe_ratio
from pybt.risk.rules import RiskConfig, RiskManager
from pybt.strategy.base import Strategy, Signal


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
    return Order(symbol=symbol, qty=delta, type="MARKET", tag="to_target", allow_partial=True, time_in_force="GTC")


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
    order_book: Dict[str, List[Dict[str, object]]] = {}

    log = logging.getLogger(__name__)
    for evt in feed:
        dt_iso = evt.dt_iso
        # 1) Gather strategy intents per symbol
        desired_targets: Dict[str, int] = {}
        weight_targets: Dict[str, float] = {}
        new_orders: Dict[str, List[Order]] = {}
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
            if isinstance(out, list):
                new_orders.setdefault(sym, []).extend([o for o in out if isinstance(o, Order)])

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
                    new_orders.setdefault(sym, []).append(od)

        # 3) Protective stops
        stop_orders = risk.protective_stop_orders(portfolio, last_close)
        for od in stop_orders:
            new_orders.setdefault(od.symbol, []).append(od)

        # 4) Execute orders for symbols present today
        for sym, bar in evt.items:
            book = order_book.setdefault(sym, [])
            if sym in new_orders:
                for order in new_orders[sym]:
                    book.append({"order": order, "remaining": order.qty})

            if not book:
                continue

            next_book: List[Dict[str, object]] = []
            for entry in book:
                order: Order = entry["order"]  # type: ignore[index]
                remaining = int(entry.get("remaining", order.qty))
                if remaining == 0:
                    continue
                tif = order.time_in_force.upper()

                temp_order = order.with_qty(remaining)
                fills_today, executed_qtys = broker.process_orders(sym, bar, portfolio.position(sym), [temp_order])
                exec_qty = executed_qtys[0] if executed_qtys else 0
                for f in fills_today:
                    portfolio.on_fill(f)
                    fills.append(f)
                    ledger.on_fill(f)
                    if log.isEnabledFor(logging.DEBUG):
                        log.debug(f"Fill {sym} {f.dt} qty={f.qty} px={f.price:.4f} comm={f.commission:.4f} tag={f.tag}")

                remaining -= exec_qty
                if remaining != 0:
                    if tif == 'GTC':
                        entry["remaining"] = remaining
                        next_book.append(entry)
                    elif tif == 'DAY':
                        # expires end of day
                        continue
                    else:  # IOC or others -> drop remainder
                        continue
            order_book[sym] = next_book

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
