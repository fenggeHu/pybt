from datetime import datetime

import pytest

from pybt.core.enums import OrderSide, OrderType
from pybt.core.event_bus import EventBus
from pybt.core.events import FillEvent, MarketEvent, OrderEvent
from pybt.execution.immediate import ImmediateExecutionHandler
from pybt.errors import ExecutionError


def test_immediate_execution_partial_fill_and_staleness_guard() -> None:
    bus = EventBus()
    exec_handler = ImmediateExecutionHandler(slippage=0.0, commission=0.0, partial_fill_ratio=0.5, max_staleness=5.0)
    exec_handler.bind(bus)
    exec_handler.on_start()

    bus.publish(MarketEvent(timestamp=datetime(2024, 1, 1, 0, 0, 0), symbol="AAA", fields={"close": 10.0}))
    bus.dispatch()

    fills: list[FillEvent] = []
    bus.subscribe(FillEvent, fills.append)

    order = OrderEvent(
        timestamp=datetime(2024, 1, 1, 0, 0, 1),
        symbol="AAA",
        quantity=100,
        order_type=OrderType.MARKET,
        direction=OrderSide.BUY,
    )
    exec_handler.on_order(order)
    bus.dispatch()

    assert fills and fills[0].quantity == 50

    stale_order = OrderEvent(
        timestamp=datetime(2024, 1, 1, 0, 0, 10),
        symbol="AAA",
        quantity=10,
        order_type=OrderType.MARKET,
        direction=OrderSide.BUY,
    )
    with pytest.raises(ExecutionError):
        exec_handler.on_order(stale_order)
