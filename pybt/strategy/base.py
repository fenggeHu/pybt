from dataclasses import dataclass
from typing import Optional

from pybt.data.bar import Bar


@dataclass
class Signal:
    """Desired target for a single instrument.

    - Set `target_units` for absolute share/contract targets (default path).
    - Alternatively set `target_weight` (fraction of equity). Requires allocator support.
    """

    target_units: Optional[int] = None
    target_weight: Optional[float] = None


class Strategy:
    def on_bar(self, bar: Bar) -> Optional[Signal]:
        """Handle a new bar.

        Return either:
          - Signal(target_units=int): engine will trade to this absolute position via market order.
          - Or a list of Order objects (see pybt.execution.order.Order) for advanced use.

        For portability, strategies should make decisions using only information
        available up to the prior close if they submit intraday-trigger orders
        (e.g., stops/limits) to avoid lookahead bias.
        """
        raise NotImplementedError
