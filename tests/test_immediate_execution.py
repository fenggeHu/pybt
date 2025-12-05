from datetime import datetime

import pytest

from pybt.core.enums import OrderSide, OrderType
from pybt.core.event_bus import EventBus
from pybt.core.events import FillEvent, MarketEvent, OrderEvent
from pybt.execution.immediate import ImmediateExecutionHandler


def test_immediate_execution_uses_cached_price_and_slippage() -> None:
    bus = EventBus()
    exec_handler = ImmediateExecutionHandler(slippage=0.1, commission=2.0)
    exec_handler.bind(bus)
    exec_handler.on_start()

    fills: list[FillEvent] = []
    bus.subscribe(FillEvent, fills.append)

    market = MarketEvent(timestamp=datetime(2024, 1, 1), symbol="AAA", fields={"close": 10.0})
    bus.publish(market)
    bus.dispatch()

    order = OrderEvent(
        timestamp=datetime(2024, 1, 1),
        symbol="AAA",
        quantity=100,
        order_type=OrderType.MARKET,
        direction=OrderSide.BUY,
    )
    exec_handler.on_order(order)
    bus.dispatch()

    assert fills and fills[0].fill_price == pytest.approx(10.1)
    assert fills[0].commission == 2.0


def test_immediate_execution_requires_price() -> None:
    bus = EventBus()
    exec_handler = ImmediateExecutionHandler()
    exec_handler.bind(bus)
    with pytest.raises(RuntimeError):
        exec_handler.on_order(
            OrderEvent(
                timestamp=datetime(2024, 1, 1),
                symbol="BBB",
                quantity=1,
                order_type=OrderType.MARKET,
                direction=OrderSide.BUY,
            )
        )
