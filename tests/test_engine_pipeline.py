from datetime import datetime, timedelta

from pybt import BacktestEngine, Bar, EngineConfig
from pybt.analytics import EquityCurveReporter
from pybt.data import InMemoryBarFeed
from pybt.execution import ImmediateExecutionHandler
from pybt.portfolio import NaivePortfolio
from pybt.risk import MaxPositionRisk
from pybt.strategies import MovingAverageCrossStrategy


def _trend_bars(symbol: str, start: datetime, periods: int) -> list[Bar]:
    bars: list[Bar] = []
    price = 100.0
    for i in range(periods):
        price += 0.5
        ts = start + timedelta(days=i)
        bars.append(
            Bar(
                symbol=symbol,
                timestamp=ts,
                open=price - 0.2,
                high=price + 0.3,
                low=price - 0.3,
                close=price,
                volume=1_000 + i,
                amount=price * (1_000 + i),
            )
        )
    return bars


def test_engine_runs_end_to_end() -> None:
    symbol = "DEMO"
    start = datetime(2024, 1, 1)
    bars = _trend_bars(symbol, start, periods=40)

    feed = InMemoryBarFeed(bars)
    strategy = MovingAverageCrossStrategy(symbol=symbol, short_window=3, long_window=8)
    portfolio = NaivePortfolio(lot_size=100)
    execution = ImmediateExecutionHandler(slippage=0.0, commission=0.0)
    risk = MaxPositionRisk(limit=500)
    reporter = EquityCurveReporter(initial_cash=50_000.0)

    engine = BacktestEngine(
        data_feed=feed,
        strategies=[strategy],
        portfolio=portfolio,
        execution=execution,
        risk_managers=[risk],
        reporters=[reporter],
        config=EngineConfig(name="test", start=start, end=bars[-1].timestamp),
    )

    engine.run()

    metrics = reporter.emit_metrics()
    assert metrics, "reporter should emit metrics after run"
    payload = next(iter(metrics)).payload
    assert "equity" in payload and payload["equity"] > 0
