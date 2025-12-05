from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, DefaultDict, Dict, Iterable, List

from pybt.core.events import FillEvent, MarketEvent, MetricsEvent
from pybt.core.interfaces import PerformanceReporter


@dataclass
class Trade:
    """单笔交易记录"""

    timestamp: datetime
    symbol: str
    quantity: int  # 正数为买入，负数为卖出
    price: float
    commission: float
    cash_flow: float  # 现金流（负数为支出，正数为收入）
    position_after: int  # 交易后的持仓
    cash_after: float  # 交易后的现金
    equity_after: float  # 交易后的总权益
    pnl: float = 0.0  # 本次交易的盈亏（仅对平仓交易有意义）


class DetailedReporter(PerformanceReporter):
    """
    详细的绩效报告器，记录所有交易并计算详细指标
    """

    def __init__(
            self, initial_cash: float = 100_000.0, track_equity_curve: bool = True
    ) -> None:
        super().__init__()
        self.initial_cash = initial_cash
        self.track_equity_curve = track_equity_curve
        self._cash: float = initial_cash
        self._positions: DefaultDict[str, int] = defaultdict(int)
        self._prices: Dict[str, float] = {}
        self._last_timestamp: datetime | None = None

        # 交易记录
        self.trades: List[Trade] = []

        # 权益曲线（可选，避免内存占用过大）
        self.equity_curve: List[tuple[datetime, float]] = []

        # 统计指标
        self._peak_equity: float = initial_cash
        self._max_drawdown: float = 0.0

        # 持仓成本跟踪（用于计算盈亏）
        self._cost_basis: DefaultDict[str, float] = defaultdict(float)

    def on_start(self) -> None:
        self._cash = self.initial_cash
        self._positions.clear()
        self._prices.clear()
        self._cost_basis.clear()
        self._last_timestamp = None
        self.trades.clear()
        self.equity_curve.clear()
        self._peak_equity = self.initial_cash
        self._max_drawdown = 0.0
        self.bus.subscribe(MarketEvent, self._on_market)

    def on_stop(self) -> None:
        self.bus.unsubscribe(MarketEvent, self._on_market)

    def on_fill(self, event: FillEvent) -> None:
        """记录成交"""
        symbol = event.symbol
        old_position = self._positions[symbol]

        # 计算本次交易的盈亏
        pnl = 0.0
        if old_position != 0:
            # 如果是平仓或减仓，计算盈亏
            if (old_position > 0 and event.quantity < 0) or (
                    old_position < 0 and event.quantity > 0
            ):
                closed_qty = min(abs(old_position), abs(event.quantity))
                avg_cost = self._cost_basis[symbol]
                pnl = closed_qty * (event.fill_price - avg_cost)
                if old_position < 0:  # 做空平仓
                    pnl = -pnl

        # 更新持仓和现金
        self._positions[symbol] += event.quantity
        cash_flow = -event.fill_price * event.quantity - event.commission
        self._cash += cash_flow
        self._last_timestamp = event.timestamp

        # 更新成本基础：区分平仓、同向加仓和反转后的建仓
        new_position = self._positions[symbol]
        if new_position == 0:
            self._cost_basis[symbol] = 0.0
        elif (new_position > 0 > old_position) or (new_position < 0 < old_position):
            # 方向反转后，剩余头寸全部来自当前成交
            self._cost_basis[symbol] = event.fill_price
        elif abs(new_position) > abs(old_position) and (new_position > 0) == (old_position > 0):
            # 同向加仓，更新加权成本
            old_cost = self._cost_basis[symbol] * abs(old_position)
            new_cost = event.fill_price * abs(event.quantity)
            self._cost_basis[symbol] = (old_cost + new_cost) / abs(new_position)

        # 计算当前权益
        equity = self._equity()

        # 记录交易
        trade = Trade(
            timestamp=event.timestamp,
            symbol=symbol,
            quantity=event.quantity,
            price=event.fill_price,
            commission=event.commission,
            cash_flow=cash_flow,
            position_after=self._positions[symbol],
            cash_after=self._cash,
            equity_after=equity,
            pnl=pnl - event.commission,  # 扣除手续费
        )
        self.trades.append(trade)

    def _on_market(self, event: MarketEvent) -> None:
        """更新市场价格和权益曲线"""
        self._prices[event.symbol] = event.fields["close"]
        self._last_timestamp = event.timestamp

        # 计算当前权益
        equity = self._equity()

        # 记录权益曲线（可选）
        if self.track_equity_curve:
            self.equity_curve.append((event.timestamp, equity))

        # 更新最大回撤
        if equity > self._peak_equity:
            self._peak_equity = equity
        if self._peak_equity > 0:
            drawdown = (self._peak_equity - equity) / self._peak_equity
            if drawdown > self._max_drawdown:
                self._max_drawdown = drawdown

    def _equity(self) -> float:
        """计算当前总权益"""
        inventory = sum(
            self._positions[symbol] * self._prices.get(symbol, 0.0)
            for symbol in self._positions
        )
        return self._cash + inventory

    def emit_metrics(self) -> Iterable[MetricsEvent]:
        """发出指标事件"""
        if self._last_timestamp is None:
            return []

        equity = self._equity()
        gross = sum(
            abs(self._positions[symbol]) * self._prices.get(symbol, 0.0)
            for symbol in self._positions
        )

        metrics = MetricsEvent(
            timestamp=self._last_timestamp,
            payload={
                "equity": equity,
                "cash": self._cash,
                "gross_exposure": gross,
                "max_drawdown": self._max_drawdown,
                "total_trades": float(len(self.trades)),
            },
        )
        return [metrics]

    def get_summary(self) -> Dict[str, Any]:
        """获取回测摘要"""
        if self._last_timestamp is None:
            return {}

        # 使用当前计算的权益，而不是依赖权益曲线
        final_equity = self._equity()
        total_return = (final_equity - self.initial_cash) / self.initial_cash

        # 计算交易统计
        buy_trades = [t for t in self.trades if t.quantity > 0]
        sell_trades = [t for t in self.trades if t.quantity < 0]
        total_commission = sum(t.commission for t in self.trades)

        # 计算盈亏统计
        closed_trades = [t for t in self.trades if t.pnl != 0]
        winning_trades = [t for t in closed_trades if t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl < 0]

        win_rate = (
            len(winning_trades) / len(closed_trades) if closed_trades else 0.0
        )
        avg_win = (
            sum(t.pnl for t in winning_trades) / len(winning_trades)
            if winning_trades
            else 0.0
        )
        avg_loss = (
            sum(t.pnl for t in losing_trades) / len(losing_trades)
            if losing_trades
            else 0.0
        )
        profit_factor = (
            abs(sum(t.pnl for t in winning_trades) / sum(t.pnl for t in losing_trades))
            if losing_trades and sum(t.pnl for t in losing_trades) != 0
            else 0.0
        )

        # 计算持仓天数
        trading_days = len(self.equity_curve) if self.track_equity_curve else 0

        return {
            "initial_cash": self.initial_cash,
            "final_equity": final_equity,
            "total_return": total_return,
            "total_return_pct": total_return * 100,
            "max_drawdown": self._max_drawdown,
            "max_drawdown_pct": self._max_drawdown * 100,
            "total_trades": len(self.trades),
            "buy_trades": len(buy_trades),
            "sell_trades": len(sell_trades),
            "closed_trades": len(closed_trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "win_rate_pct": win_rate * 100,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "total_commission": total_commission,
            "total_pnl": sum(t.pnl for t in closed_trades),
            "trading_days": trading_days,
            "final_cash": self._cash,
            "final_positions": dict(self._positions),
        }

    def print_summary(self) -> None:
        """打印回测摘要"""
        summary = self.get_summary()
        if not summary:
            print("无回测数据")
            return

        print("\n" + "=" * 60)
        print("回测摘要".center(60))
        print("=" * 60)

        print(f"\n初始资金: {summary['initial_cash']:,.2f}")
        print(f"最终权益: {summary['final_equity']:,.2f}")
        print(f"总收益: {summary['final_equity'] - summary['initial_cash']:,.2f}")
        print(f"收益率: {summary['total_return_pct']:.2f}%")
        print(f"最大回撤: {summary['max_drawdown_pct']:.2f}%")

        print(f"\n交易统计:")
        print(f"  总交易次数: {summary['total_trades']}")
        print(f"  买入次数: {summary['buy_trades']}")
        print(f"  卖出次数: {summary['sell_trades']}")
        print(f"  平仓次数: {summary['closed_trades']}")
        print(f"  盈利次数: {summary['winning_trades']}")
        print(f"  亏损次数: {summary['losing_trades']}")
        print(f"  胜率: {summary['win_rate_pct']:.2f}%")
        if summary["avg_win"] != 0 or summary["avg_loss"] != 0:
            print(f"  平均盈利: {summary['avg_win']:,.2f}")
            print(f"  平均亏损: {summary['avg_loss']:,.2f}")
            if summary["profit_factor"] > 0:
                print(f"  盈亏比: {summary['profit_factor']:.2f}")
        print(f"  总盈亏: {summary['total_pnl']:,.2f}")
        print(f"  总手续费: {summary['total_commission']:,.2f}")

        print(f"\n最终状态:")
        print(f"  现金余额: {summary['final_cash']:,.2f}")
        if summary["final_positions"]:
            print(f"  持仓:")
            for symbol, qty in summary["final_positions"].items():
                if qty != 0:
                    value = qty * self._prices.get(symbol, 0.0)
                    print(f"    {symbol}: {qty} 股 (市值: {value:,.2f})")

        print("=" * 60)

    def print_trades(self, limit: int = 20) -> None:
        """打印交易明细"""
        if not self.trades:
            print("\n无交易记录")
            return

        print("\n" + "=" * 100)
        print("交易明细".center(100))
        print("=" * 100)
        print(
            f"{'时间':<12} {'股票':<8} {'方向':<4} {'数量':<6} "
            f"{'价格':<8} {'手续费':<8} {'盈亏':<10} {'持仓':<6} {'权益':<12}"
        )
        print("-" * 100)

        trades_to_show = (
            self.trades[-limit:] if len(self.trades) > limit else self.trades
        )

        for trade in trades_to_show:
            direction = "买入" if trade.quantity > 0 else "卖出"
            pnl_str = f"{trade.pnl:,.2f}" if trade.pnl != 0 else "-"
            print(
                f"{trade.timestamp.strftime('%Y-%m-%d'):<12} "
                f"{trade.symbol:<8} "
                f"{direction:<4} "
                f"{abs(trade.quantity):<6} "
                f"{trade.price:<8.2f} "
                f"{trade.commission:<8.2f} "
                f"{pnl_str:<10} "
                f"{trade.position_after:<6} "
                f"{trade.equity_after:<12.2f}"
            )

        if len(self.trades) > limit:
            print(f"\n... 仅显示最近 {limit} 笔交易，共 {len(self.trades)} 笔")

        print("=" * 100)
