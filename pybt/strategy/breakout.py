from __future__ import annotations

from collections import deque
from typing import Deque, List, Optional

from pybt.data.bar import Bar
from pybt.execution.order import Order
from .base import Strategy


class DonchianBreakout(Strategy):
    """Donchian breakout using prior N bars (excludes current bar).

    - If flat: place stop buy at prior N-high and stop sell at prior N-low.
    - If long: place stop sell (exit) at prior N-low.
    - If short: place stop buy-to-cover at prior N-high.
    Quantity is +/-1 unit by default.
    """

    def __init__(self, symbol: str, lookback: int = 20, qty: int = 1, allow_short: bool = True):
        assert lookback >= 2
        self.symbol = symbol
        self.N = lookback
        self.qty = int(qty)
        self.allow_short = allow_short
        self.hbuf: Deque[float] = deque(maxlen=lookback)
        self.lbuf: Deque[float] = deque(maxlen=lookback)
        self.position: int = 0  # strategy-local view; engine can also consult portfolio

    def on_bar(self, bar: Bar):
        # Compute breakout levels from prior N bars (exclude current), so use buffers before updating
        orders: List[Order] = []
        if len(self.hbuf) == self.N and len(self.lbuf) == self.N:
            prior_high = max(self.hbuf)
            prior_low = min(self.lbuf)
            if self.position == 0:
                # place both side stops
                orders.append(Order(symbol=self.symbol, qty=+self.qty, type="STOP", stop_price=prior_high, tag="breakout_up"))
                if self.allow_short:
                    orders.append(Order(symbol=self.symbol, qty=-self.qty, type="STOP", stop_price=prior_low, tag="breakout_down"))
            elif self.position > 0:
                # long: stop exit
                orders.append(Order(symbol=self.symbol, qty=-self.qty, type="STOP", stop_price=prior_low, tag="stop_exit_long"))
            elif self.position < 0:
                # short: stop exit
                orders.append(Order(symbol=self.symbol, qty=+self.qty, type="STOP", stop_price=prior_high, tag="stop_exit_short"))

        # Update buffers with current bar at the end
        self.hbuf.append(bar.high)
        self.lbuf.append(bar.low)
        return orders if orders else None

    # Optional hooks for engine to sync position
    def sync_position(self, units: int) -> None:
        self.position = int(units)

