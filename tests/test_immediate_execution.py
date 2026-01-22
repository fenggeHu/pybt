from datetime import datetime

import pytest

from pybt.core.enums import OrderSide, OrderType
from pybt.core.event_bus import EventBus
from pybt.core.events import FillEvent, MarketEvent, OrderEvent
from pybt.execution.immediate import FillTiming, ImmediateExecutionHandler
from pybt.errors import ExecutionError


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
    with pytest.raises(ExecutionError):
        exec_handler.on_order(
            OrderEvent(
                timestamp=datetime(2024, 1, 1),
                symbol="BBB",
                quantity=1,
                order_type=OrderType.MARKET,
                direction=OrderSide.BUY,
            )
        )


def test_immediate_execution_next_open_defers_fill_until_next_bar() -> None:
    bus = EventBus()
    exec_handler = ImmediateExecutionHandler(fill_timing=FillTiming.NEXT_OPEN)
    exec_handler.bind(bus)
    exec_handler.on_start()

    fills: list[FillEvent] = []
    bus.subscribe(FillEvent, fills.append)

    # First bar arrives; strategy/order happens on this bar, but fill should happen on next bar open.
    bus.publish(
        MarketEvent(
            timestamp=datetime(2024, 1, 1),
            symbol="AAA",
            fields={"open": 9.5, "close": 10.0},
        )
    )
    bus.dispatch()

    exec_handler.on_order(
        OrderEvent(
            timestamp=datetime(2024, 1, 1),
            symbol="AAA",
            quantity=1,
            order_type=OrderType.MARKET,
            direction=OrderSide.BUY,
        )
    )
    bus.dispatch()
    assert fills == []

    # Next bar arrives; pending order is filled at this bar's open.
    bus.publish(
        MarketEvent(
            timestamp=datetime(2024, 1, 2),
            symbol="AAA",
            fields={"open": 11.0, "close": 11.5},
        )
    )
    bus.dispatch()

    assert len(fills) == 1
    assert fills[0].timestamp == datetime(2024, 1, 2)
    assert fills[0].fill_price == pytest.approx(11.0)
