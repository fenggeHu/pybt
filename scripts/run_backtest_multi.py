#!/usr/bin/env python3


import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pybt.execution.broker import SimBroker
from pybt.engine.multi import run_backtest_multi
from pybt.portfolio.multi import MultiPortfolio
from pybt.risk.rules import RiskConfig, RiskManager
from pybt.research.api import load_dir_csvs
from pybt.strategy.sma_crossover import SmaCrossStrategy
from pybt.config import load_config
from pybt.analytics.export import export_equity_csv, export_metrics_json, export_trades_csv
from pybt.analytics.report import trade_stats, period_returns


def main() -> None:
    ap = argparse.ArgumentParser(description="Run a multi-symbol backtest with SMA crossover per symbol")
    ap.add_argument("--data-dir", type=str, default="data", help="Directory with CSVs: one per symbol")
    ap.add_argument("--fast", type=int, default=10)
    ap.add_argument("--slow", type=int, default=30)
    ap.add_argument("--allow-short", action="store_true")
    ap.add_argument("--cash", type=float, default=100_000.0)
    ap.add_argument("--slip-bps", type=float, default=1.0)
    ap.add_argument("--comm", type=float, default=0.0, help="Commission per share")
    ap.add_argument("--comm-rate", type=float, default=0.0, help="Commission as rate of notional")
    ap.add_argument("--volume-limit", type=float, default=1.0, help="Max fraction of daily volume used per order (0-1)")
    ap.add_argument("--max-units", type=int, default=100)
    ap.add_argument("--stop-pct", type=float, default=0.0, help="Protective stop loss percent, e.g. 0.1 for 10%")
    ap.add_argument("--rf-daily", type=float, default=0.0, help="Daily interest on positive cash (e.g. 0.0001)")
    ap.add_argument("--borrow-daily", type=float, default=0.0, help="Daily interest on negative cash (e.g. 0.0003)")
    ap.add_argument("--out-dir", type=str, default="", help="Export equity/trades/metrics to this directory")
    ap.add_argument("--config", type=str, default="", help="Optional JSON config file (keys match CLI args)")
    ap.add_argument("--log", type=str, default="WARNING", help="Logging level: DEBUG,INFO,WARNING,ERROR,CRITICAL")
    args = ap.parse_args()

    if args.config:
        try:
            cfg = load_config(args.config)
            for k, v in cfg.items():
                if hasattr(args, k) and getattr(args, k) == ap.get_default(k):
                    setattr(args, k, v)
        except Exception as e:
            print(f"Failed to load config {args.config}: {e}")

    logging.basicConfig(level=getattr(logging, args.log.upper(), logging.WARNING), format='[%(levelname)s] %(message)s')

    data = load_dir_csvs(args.data_dir)
    if not data:
        print(f"No CSVs found in {args.data_dir}. Please put files like AAPL.csv, MSFT.csv.")
        return

    strategies = {sym: SmaCrossStrategy(args.fast, args.slow, args.allow_short) for sym in data.keys()}
    broker = SimBroker(
        slippage_bps=args.slip_bps,
        commission_per_share=args.comm,
        commission_rate=args.comm_rate,
        volume_limit_pct=args.volume_limit,
    )
    port = MultiPortfolio(initial_cash=args.cash, rf_daily=args.rf_daily, borrow_daily=args.borrow_daily)
    risk = RiskManager(RiskConfig(max_units_per_symbol=args.max_units, stop_loss_pct=args.stop_pct))

    res = run_backtest_multi(data, strategies, portfolio=port, broker=broker, risk=risk)

    m = dict(res.metrics)
    ts = trade_stats([type('T', (), t) for t in res.trades]) if res.trades else {}
    for k, v in ts.items():
        m[f"trade_{k}"] = v
    monthly = period_returns(res.equity_curve, period='M')
    m["monthly_count"] = float(len(monthly))

    print("Metrics:")
    core_order = ["total_return", "cagr", "sharpe", "max_drawdown"]
    for k in core_order:
        if k not in m:
            continue
        v = m[k]
        if k in ("sharpe", "max_drawdown"):
            print(f"  {k:>13}: {v:.3f}")
        else:
            print(f"  {k:>13}: {v * 100:.2f}%")

    if res.trades:
        print("Trade Stats:")

        def fmt_pct(x: float) -> str:
            return f"{x * 100:.2f}%"

        print(f"  {'trades':>13}: {int(m.get('trade_trades', 0))}")
        print(f"  {'win_rate':>13}: {fmt_pct(m.get('trade_win_rate', 0.0))}")
        print(f"  {'avg_win':>13}: {m.get('trade_avg_win', 0.0):.2f}")
        print(f"  {'avg_loss':>13}: {m.get('trade_avg_loss', 0.0):.2f}")
        print(f"  {'profit_factor':>13}: {m.get('trade_profit_factor', 0.0):.2f}")
        print(f"  {'avg_ret':>13}: {fmt_pct(m.get('trade_avg_ret', 0.0))}")
        print(f"  {'avg_hold_days':>13}: {m.get('trade_avg_hold_days', 0.0):.2f}")
        print(f"  {'monthly_count':>13}: {int(m.get('monthly_count', 0))}")
    print("Equity (last 5):")
    for dt, eq in res.equity_curve[-5:]:
        print(f"  {dt}  {eq:,.2f}")

    if args.out_dir:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        export_equity_csv(str(out / 'equity.csv'), res.equity_curve)
        export_trades_csv(str(out / 'trades.csv'), [type('T', (), t) for t in res.trades])
        export_metrics_json(str(out / 'metrics.json'), m)
        print(f"Exported results to {out}")


if __name__ == "__main__":
    main()
