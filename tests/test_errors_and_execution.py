import pytest

from pybt import ExecutionError, PyBTError
from pybt.execution.immediate import ImmediateExecutionHandler
from pybt.core.events import OrderEvent
from pybt.core.enums import OrderSide, OrderType
from pybt.core.event_bus import EventBus


def test_exception_hierarchy():
    assert issubclass(ExecutionError, PyBTError)


def test_immediate_execution_raises_execution_error_when_no_price():
    bus = EventBus()
    handler = ImmediateExecutionHandler()
    handler.bind(bus)
    with pytest.raises(ExecutionError):
        handler.on_order(
            OrderEvent(
                timestamp=__import__("datetime").datetime.utcnow(),
                symbol="AAA",
                quantity=1,
                order_type=OrderType.MARKET,
                direction=OrderSide.BUY,
            )
        )
