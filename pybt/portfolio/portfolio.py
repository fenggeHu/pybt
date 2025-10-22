from dataclasses import dataclass, field
from typing import List, Tuple

from pybt.data.bar import Bar
from pybt.execution.broker import Fill


@dataclass
class Portfolio:
    initial_cash: float = 100_000.0
    cash: float = field(init=False)
    units: int = field(init=False, default=0)
    equity_curve: List[Tuple[str, float]] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self.cash = float(self.initial_cash)

    def on_fill(self, fill: Fill) -> None:
        # Update cash and position given a fill
        dollars = fill.qty * fill.price
        self.cash -= dollars  # buy reduces cash, sell increases (qty negative)
        self.cash -= fill.commission
        self.units += fill.qty

    def mark_to_market(self, bar: Bar) -> float:
        equity = self.cash + self.units * bar.close
        self.equity_curve.append((bar.dt.isoformat(), equity))
        return equity
