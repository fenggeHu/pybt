"""
使用 adata 进行多股票轮动策略回测

依赖安装:
    pip install adata pandas

示例说明:
    - 获取多只 A 股的历史数据
    - 实现简单的动量轮动策略
    - 每月选择表现最好的股票持有
"""

from collections import defaultdict
from datetime import datetime
from typing import Dict, List

import adata

from pybt import (
    BacktestEngine,
    Bar,
    DetailedReporter,
    EngineConfig,
    MarketEvent,
    OrderSide,
    SignalDirection,
    SignalEvent,
)
from pybt.core.interfaces import Strategy
from pybt.data import InMemoryBarFeed
from pybt.execution import ImmediateExecutionHandler
from pybt.portfolio import NaivePortfolio
from pybt.risk import MaxPositionRisk


def fetch_multiple_stocks(
    stock_codes: List[str],
    start_date: str,
    end_date: str,
) -> List[Bar]:
    """
    获取多只股票的历史数据

    Args:
        stock_codes: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        所有股票的 Bar 对象列表（已排序）
    """
    all_bars: List[Bar] = []

    for stock_code in stock_codes:
        print(f"正在获取 {stock_code} 的数据...")
        try:
            df = adata.stock.market.get_market(
                stock_code=stock_code,
                start_date=start_date,
                end_date=end_date,
            )

            if df is None or df.empty:
                print(f"  警告: 无法获取 {stock_code} 的数据，跳过")
                continue

            for _, row in df.iterrows():
                # 处理日期格式，支持 'YYYYMMDD' 和 'YYYY-MM-DD' 两种格式
                trade_date_str = str(row["trade_date"])
                if "-" in trade_date_str:
                    timestamp = datetime.strptime(trade_date_str, "%Y-%m-%d")
                else:
                    timestamp = datetime.strptime(trade_date_str, "%Y%m%d")
                
                bar = Bar(
                    symbol=stock_code,
                    timestamp=timestamp,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                    amount=float(row.get("amount", 0.0)),  # 成交额，如果没有则为0
                )
                all_bars.append(bar)

            print(f"  成功获取 {len(df)} 条数据")

        except Exception as e:
            print(f"  错误: {e}")
            continue

    # 按时间排序
    all_bars.sort(key=lambda x: x.timestamp)
    return all_bars


class MomentumRotationStrategy(Strategy):
    """
    动量轮动策略

    每隔 rebalance_days 天，计算各股票的动量（过去 lookback_days 天的收益率），
    选择动量最高的股票持有，卖出其他股票。
    """

    def __init__(
        self,
        symbols: List[str],
        lookback_days: int = 20,
        rebalance_days: int = 20,
    ) -> None:
        super().__init__()
        self.symbols = symbols
        self.lookback_days = lookback_days
        self.rebalance_days = rebalance_days

        # 存储每个股票的价格历史
        self._price_history: Dict[str, List[tuple[datetime, float]]] = defaultdict(list)
        self._last_rebalance: datetime | None = None
        self._current_holding: str | None = None

    def on_market(self, event: MarketEvent) -> None:
        """处理市场数据"""
        symbol = event.symbol
        close_price = event.fields["close"]
        timestamp = event.timestamp

        # 记录价格
        self._price_history[symbol].append((timestamp, close_price))

        # 只保留需要的历史数据
        max_history = self.lookback_days + 10
        if len(self._price_history[symbol]) > max_history:
            self._price_history[symbol] = self._price_history[symbol][-max_history:]

        # 检查是否需要重新平衡
        if self._should_rebalance(timestamp):
            self._rebalance(timestamp)

    def _should_rebalance(self, timestamp: datetime) -> bool:
        """判断是否需要重新平衡"""
        if self._last_rebalance is None:
            return True

        days_since_rebalance = (timestamp - self._last_rebalance).days
        return days_since_rebalance >= self.rebalance_days

    def _rebalance(self, timestamp: datetime) -> None:
        """执行重新平衡"""
        # 计算每个股票的动量
        momentum_scores: Dict[str, float] = {}

        for symbol in self.symbols:
            history = self._price_history[symbol]
            if len(history) < self.lookback_days:
                continue

            # 获取 lookback_days 天前的价格
            old_price = None
            for ts, price in history:
                if (timestamp - ts).days >= self.lookback_days:
                    old_price = price
                    break

            if old_price is None or old_price <= 0:
                continue

            # 计算收益率作为动量指标
            current_price = history[-1][1]
            momentum = (current_price - old_price) / old_price
            momentum_scores[symbol] = momentum

        if not momentum_scores:
            return

        # 选择动量最高的股票
        best_symbol = max(momentum_scores, key=momentum_scores.get)

        # 如果当前持有的不是最佳股票，则调整持仓
        if self._current_holding != best_symbol:
            # 先卖出当前持仓
            if self._current_holding is not None:
                exit_signal = SignalEvent(
                    timestamp=timestamp,
                    symbol=self._current_holding,
                    direction=SignalDirection.EXIT,
                )
                self.bus.publish(exit_signal)

            # 买入新股票
            long_signal = SignalEvent(
                timestamp=timestamp,
                symbol=best_symbol,
                direction=SignalDirection.LONG,
            )
            self.bus.publish(long_signal)

            print(
                f"\n[{timestamp.date()}] 轮动: {self._current_holding or '空仓'} -> {best_symbol} "
                f"(动量: {momentum_scores[best_symbol]:.2%})"
            )

            self._current_holding = best_symbol

        self._last_rebalance = timestamp


def main() -> None:
    """主回测流程"""
    # ========== 配置参数 ==========
    # 选择几只银行股进行轮动
    stock_codes = [
        "000001",  # 平安银行
        "600036",  # 招商银行
        "601166",  # 兴业银行
        "600000",  # 浦发银行
    ]
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    initial_cash = 100_000.0
    lot_size = 100
    max_position = 1000

    # ========== 获取数据 ==========
    print("开始获取数据...\n")
    try:
        bars = fetch_multiple_stocks(stock_codes, start_date, end_date)
    except Exception as e:
        print(f"获取数据失败: {e}")
        print("\n请确保已安装 adata: pip install adata")
        return

    if not bars:
        print("未获取到任何数据")
        return

    print(f"\n总共获取 {len(bars)} 条数据")
    print(f"数据范围: {bars[0].timestamp.date()} 至 {bars[-1].timestamp.date()}")

    # ========== 构建回测组件 ==========
    feed = InMemoryBarFeed(bars)
    strategy = MomentumRotationStrategy(
        symbols=stock_codes,
        lookback_days=20,
        rebalance_days=20,
    )
    portfolio = NaivePortfolio(lot_size=lot_size)
    execution = ImmediateExecutionHandler(slippage=0.001, commission=5.0)
    risk = MaxPositionRisk(limit=max_position)
    reporter = DetailedReporter(initial_cash=initial_cash)

    # ========== 运行回测 ==========
    engine = BacktestEngine(
        data_feed=feed,
        strategies=[strategy],
        portfolio=portfolio,
        execution=execution,
        risk_managers=[risk],
        reporters=[reporter],
        config=EngineConfig(
            name="momentum_rotation",
            start=bars[0].timestamp,
            end=bars[-1].timestamp,
        ),
    )

    print(f"\n========== 开始回测 ==========")
    print(f"策略: 动量轮动")
    print(f"股票池: {', '.join(stock_codes)}")
    print(f"初始资金: {initial_cash:,.2f}")

    engine.run()

    # ========== 输出结果 ==========
    # 打印详细摘要
    reporter.print_summary()

    # 打印交易明细
    reporter.print_trades(limit=30)


if __name__ == "__main__":
    main()
