from datetime import datetime

from pybt.analytics.detailed import DetailedReporter
from pybt.core.event_bus import EventBus
from pybt.core.events import FillEvent


def test_cost_basis_updates_on_reversal_and_additional_fills() -> None:
    reporter = DetailedReporter(initial_cash=100_000.0, track_equity_curve=False)
    bus = EventBus()
    reporter.bind(bus)
    reporter.on_start()

    ts = datetime(2024, 1, 1)

    # 开仓做空 100 股 @10
    reporter.on_fill(
        FillEvent(timestamp=ts, order_id="1", symbol="XYZ", quantity=-100, fill_price=10.0)
    )

    # 反手买入 200 股 @12 -> 先平 100 空，再做多 100，成本应重置为 12
    reporter.on_fill(
        FillEvent(timestamp=ts, order_id="2", symbol="XYZ", quantity=200, fill_price=12.0)
    )
    assert reporter._cost_basis["XYZ"] == 12.0
    assert reporter.trades[1].pnl == -200.0

    # 同向加仓 100 股 @13，成本加权到 12.5
    reporter.on_fill(
        FillEvent(timestamp=ts, order_id="3", symbol="XYZ", quantity=100, fill_price=13.0)
    )
    assert reporter._cost_basis["XYZ"] == 12.5

    # 部分卖出 50 股 @14，检查盈亏
    reporter.on_fill(
        FillEvent(timestamp=ts, order_id="4", symbol="XYZ", quantity=-50, fill_price=14.0)
    )
    assert reporter.trades[-1].pnl == 75.0
