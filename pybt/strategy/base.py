
from dataclasses import dataclass
from typing import Optional

from pybt.data.bar import Bar


@dataclass
class Signal:
    """Desired target position in units for a single instrument.

    This is purposely simple (single-symbol demo). Positive = long, negative = short.
    """

    target_units: int


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
