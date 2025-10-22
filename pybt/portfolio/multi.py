from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from pybt.data.bar import Bar
from pybt.execution.broker import Fill


@dataclass
class MultiPortfolio:
    initial_cash: float = 100_000.0
    cash: float = field(init=False)
    positions: Dict[str, int] = field(init=False, default_factory=dict)
    entry_price: Dict[str, float] = field(init=False, default_factory=dict)  # cost basis for current side
    equity_curve: List[Tuple[str, float]] = field(init=False, default_factory=list)
    rf_daily: float = 0.0         # interest earned on positive cash
    borrow_daily: float = 0.0     # interest paid on negative cash

    def __post_init__(self) -> None:
        self.cash = float(self.initial_cash)

    def position(self, symbol: str) -> int:
        return int(self.positions.get(symbol, 0))

    def on_fill(self, fill: Fill) -> None:
        # Cash impact
        dollars = fill.qty * fill.price
        self.cash -= dollars
        self.cash -= fill.commission

        # Position update
        sym = fill.symbol
        old = self.positions.get(sym, 0)
        new = old + fill.qty
        self.positions[sym] = new

        # Update entry price for current side
        if old == 0 or (old > 0 and new < 0) or (old < 0 and new > 0):
            # Open new side or flip
            if new != 0:
                self.entry_price[sym] = fill.price
            else:
                self.entry_price.pop(sym, None)
        else:
            # Same side add/reduce: update to weighted average price
            if new != 0:
                # Weighted by absolute units on side; if reducing, keep prior entry
                if (old > 0 and new > 0) or (old < 0 and new < 0):
                    w_old = abs(old)
                    w_new = abs(fill.qty)
                    if w_old + w_new > 0:
                        prev = self.entry_price.get(sym, fill.price)
                        self.entry_price[sym] = (prev * w_old + fill.price * w_new) / (w_old + w_new)
                else:
                    # crossed through zero handled above
                    pass
            else:
                self.entry_price.pop(sym, None)

    def mark_to_market(self, dt_iso: str, prices: Dict[str, float]) -> float:
        # Apply daily financing on cash prior to equity snapshot
        if self.cash != 0.0:
            rate = self.rf_daily if self.cash > 0 else -self.borrow_daily
            self.cash += self.cash * rate
        equity = self.cash
        for sym, units in self.positions.items():
            px = prices.get(sym)
            if px is not None:
                equity += units * px
        self.equity_curve.append((dt_iso, equity))
        return equity

    def total_equity(self, prices: Dict[str, float]) -> float:
        equity = self.cash
        for sym, units in self.positions.items():
            px = prices.get(sym)
            if px is not None:
                equity += units * px
        return equity
