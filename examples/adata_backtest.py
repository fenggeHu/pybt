"""
使用 adata 数据源的真实回测示例

依赖安装:
    pip install adata

示例说明:
    - 使用 adata 获取 A 股真实历史数据
    - 实现双均线交叉策略
    - 展示完整的回测流程和结果
"""

from datetime import datetime
from typing import List

import adata

from pybt import BacktestEngine, Bar, DetailedReporter, EngineConfig
from pybt.data import InMemoryBarFeed
from pybt.execution import ImmediateExecutionHandler
from pybt.portfolio import NaivePortfolio
from pybt.risk import MaxPositionRisk
from pybt.strategies import MovingAverageCrossStrategy


def fetch_stock_data(
        stock_code: str,
        start_date: str,
        end_date: str,
) -> List[Bar]:
    """
    使用 adata 获取股票历史数据并转换为 Bar 对象

    Args:
        stock_code: 股票代码，如 '000001' (平安银行)
        start_date: 开始日期，格式 'YYYY-MM-DD'
        end_date: 结束日期，格式 'YYYY-MM-DD'

    Returns:
        Bar 对象列表
    """
    print(f"正在获取 {stock_code} 从 {start_date} 到 {end_date} 的数据...")

    # 使用 adata 获取日线数据
    df = adata.stock.market.get_market(
        stock_code=stock_code,
        start_date=start_date,
        end_date=end_date,
    )

    if df is None or df.empty:
        raise ValueError(f"无法获取股票 {stock_code} 的数据")

    print(f"成功获取 {len(df)} 条数据")

    # 转换为 Bar 对象
    bars: List[Bar] = []
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
        )
        bars.append(bar)

    # 按时间排序
    bars.sort(key=lambda x: x.timestamp)
    return bars


def main() -> None:
    """
    主回测流程
    """
    # ========== 配置参数 ==========
    stock_code = "300502"
    start_date = "2025-09-01"
    end_date = "2025-10-31"
    initial_cash = 100_000.0  # 初始资金 10 万
    lot_size = 100  # 每次交易 100 股
    max_position = 1000  # 最大持仓 1000 股
    short_window = 5  # 短期均线周期
    long_window = 20  # 长期均线周期

    # ========== 获取数据 ==========
    try:
        bars = fetch_stock_data(stock_code, start_date, end_date)
    except Exception as e:
        print(f"获取数据失败: {e}")
        print("\n请确保已安装 adata: pip install adata")
        return

    if len(bars) < long_window:
        print(f"数据不足，至少需要 {long_window} 条数据")
        return

    print(f"\n数据范围: {bars[0].timestamp.date()} 至 {bars[-1].timestamp.date()}")
    print(f"起始价格: {bars[0].close:.2f}")
    print(f"结束价格: {bars[-1].close:.2f}")
    print(f"价格变化: {(bars[-1].close / bars[0].close - 1) * 100:.2f}%")

    # ========== 构建回测组件 ==========
    feed = InMemoryBarFeed(bars)
    strategy = MovingAverageCrossStrategy(
        symbol=stock_code,
        short_window=short_window,
        long_window=long_window,
    )
    portfolio = NaivePortfolio(lot_size=lot_size)
    execution = ImmediateExecutionHandler(
        slippage=0.001,  # 0.1% 滑点
        commission=5.0,  # 每笔交易 5 元手续费
    )
    risk = MaxPositionRisk(limit=max_position)
    reporter = DetailedReporter(initial_cash=initial_cash)

    # ========== 创建并运行回测引擎 ==========
    engine = BacktestEngine(
        data_feed=feed,
        strategies=[strategy],
        portfolio=portfolio,
        execution=execution,
        risk_managers=[risk],
        reporters=[reporter],
        config=EngineConfig(
            name=f"{stock_code}_ma_cross",
            start=bars[0].timestamp,
            end=bars[-1].timestamp,
        ),
    )

    print(f"\n========== 开始回测 ==========")
    print(f"策略: 双均线交叉 (短期={short_window}, 长期={long_window})")
    print(f"初始资金: {initial_cash:,.2f}")
    print(f"每次交易: {lot_size} 股")
    print(f"最大持仓: {max_position} 股")

    engine.run()

    # ========== 输出结果 ==========
    # 打印详细摘要
    reporter.print_summary()

    # 打印交易明细
    reporter.print_trades(limit=30)

    # 计算买入持有策略的收益率
    summary = reporter.get_summary()
    if summary:
        buy_hold_return = (bars[-1].close / bars[0].close - 1) * 100
        print(f"\n买入持有收益率: {buy_hold_return:.2f}%")
        print(
            f"策略超额收益: {summary['total_return_pct'] - buy_hold_return:.2f}%"
        )


if __name__ == "__main__":
    main()
