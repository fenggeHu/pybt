import unittest
from datetime import datetime, timedelta

from pybt.data.bar import Bar
from pybt.data.loader import generate_synthetic
from pybt.engine.backtester import run_backtest
from pybt.engine.multi import run_backtest_multi
from pybt.execution.broker import SimBroker
from pybt.portfolio.multi import MultiPortfolio
from pybt.portfolio.portfolio import Portfolio
from pybt.strategy.base import Signal, Strategy
from pybt.strategy.sma_crossover import SmaCrossStrategy


class TestEngine(unittest.TestCase):
    def test_run_backtest(self):
        bars = generate_synthetic(days=120)
        strat = SmaCrossStrategy(5, 20)
        res = run_backtest(bars, strat, Portfolio(100000), SimBroker())
        self.assertIn('total_return', res.metrics)
        self.assertTrue(len(res.equity_curve) > 0)

    def test_gtc_orders_fill_over_time(self):
        class TargetStrategy(Strategy):
            def __init__(self):
                self.emitted = False

            def on_bar(self, bar: Bar):
                if not self.emitted:
                    self.emitted = True
                    return Signal(target_units=10)
                return None

        start = datetime(2022, 1, 3)
        bars = []
        price = 100.0
        for i in range(6):
            dt = start + timedelta(days=i)
            bars.append(
                Bar(
                    dt=dt,
                    open=price,
                    high=price * 1.01,
                    low=price * 0.99,
                    close=price,
                    volume=10.0,
                )
            )

        data = {"XYZ": bars}
        strat = TargetStrategy()
        port = MultiPortfolio(initial_cash=100_000.0)
        broker = SimBroker(volume_limit_pct=0.2)  # at most 2 shares per day

        run_backtest_multi(data, {"XYZ": strat}, portfolio=port, broker=broker)

        self.assertEqual(port.position("XYZ"), 10)


if __name__ == '__main__':
    unittest.main()
