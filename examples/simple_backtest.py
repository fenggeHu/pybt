from datetime import datetime, timedelta
from typing import List

from pybt import BacktestEngine, Bar, EngineConfig
from pybt.analytics import EquityCurveReporter
from pybt.data import InMemoryBarFeed
from pybt.execution import ImmediateExecutionHandler
from pybt.portfolio import NaivePortfolio
from pybt.risk import MaxPositionRisk
from pybt.strategies import MovingAverageCrossStrategy


def synthetic_bars(symbol: str, start: datetime, periods: int) -> List[Bar]:
    bars: List[Bar] = []
    price = 100.0
    for step in range(periods):
        timestamp = start + timedelta(days=step)
        price += (1 if step % 5 < 3 else -1) * 0.8  # basic waveform
        volume = 1_000 + step * 10
        bar = Bar(
            symbol=symbol,
            timestamp=timestamp,
            open=price - 0.4,
            high=price + 0.6,
            low=price - 0.6,
            close=price,
            volume=volume,
            amount=price * volume,  # 成交额 = 价格 * 成交量
        )
        bars.append(bar)
    return bars


def main() -> None:
    symbol = "TEST"
    start = datetime(2022, 1, 1)
    bars = synthetic_bars(symbol, start, periods=120)

    feed = InMemoryBarFeed(bars)
    strategy = MovingAverageCrossStrategy(
        symbol=symbol, short_window=5, long_window=20)
    portfolio = NaivePortfolio(lot_size=100)
    execution = ImmediateExecutionHandler(slippage=0.02, commission=1.0)
    risk = MaxPositionRisk(limit=500)
    reporter = EquityCurveReporter(initial_cash=100_000.0)

    engine = BacktestEngine(
        data_feed=feed,
        strategies=[strategy],
        portfolio=portfolio,
        execution=execution,
        risk_managers=[risk],
        reporters=[reporter],
        config=EngineConfig(name="demo", start=start, end=bars[-1].timestamp),
    )

    engine.run()

    final_metrics = list(reporter.emit_metrics())
    if final_metrics:
        metrics = final_metrics[-1]
        print("Final metrics:")
        for key, value in metrics.payload.items():
            print(f"  {key}: {value:.2f}")


if __name__ == "__main__":
    main()
