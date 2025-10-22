#!/usr/bin/env python3

import argparse
import os
import sys
import logging
from pathlib import Path

# Allow running from the repo without installing the package
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pybt.data.loader import DataSpec, generate_synthetic, load_csv
from pybt.engine.backtester import run_backtest
from pybt.analytics.export import export_equity_csv, export_metrics_json, export_trades_csv
from pybt.analytics.report import trade_stats, period_returns
from pybt.config import load_config
from pybt.execution.broker import SimBroker
from pybt.portfolio.portfolio import Portfolio
from pybt.strategy.sma_crossover import SmaCrossStrategy


def main() -> None:
    ap = argparse.ArgumentParser(description="Run a simple SMA crossover backtest")
    ap.add_argument("--csv", type=str, default="data/SPY_sample.csv", help="Path to CSV with date,open,high,low,close,volume")
    ap.add_argument("--fast", type=int, default=10)
    ap.add_argument("--slow", type=int, default=30)
    ap.add_argument("--allow-short", action="store_true")
    ap.add_argument("--cash", type=float, default=100_000.0)
    ap.add_argument("--slip-bps", type=float, default=1.0)
    ap.add_argument("--comm", type=float, default=0.0, help="Commission per share")
    ap.add_argument("--out-dir", type=str, default="", help="Export equity/trades/metrics to this directory")
    ap.add_argument("--config", type=str, default="", help="Optional JSON config file (keys match CLI args)")
    ap.add_argument("--log", type=str, default="WARNING", help="Logging level: DEBUG,INFO,WARNING,ERROR,CRITICAL")
    args = ap.parse_args()

    # Apply config as defaults; CLI overrides
    if args.config:
        try:
            cfg = load_config(args.config)
            for k, v in cfg.items():
                if hasattr(args, k) and getattr(args, k) == ap.get_default(k):
                    setattr(args, k, v)
        except Exception as e:
            print(f"Failed to load config {args.config}: {e}")

    logging.basicConfig(level=getattr(logging, args.log.upper(), logging.WARNING), format='[%(levelname)s] %(message)s')

    path = Path(args.csv)
    if path.exists():
        bars = load_csv(DataSpec(path=path))
    else:
        print(f"CSV not found at {path}, generating synthetic data...")
        bars = generate_synthetic(days=500)

    strat = SmaCrossStrategy(fast=args.fast, slow=args.slow, allow_short=args.allow_short)
    broker = SimBroker(slippage_bps=args.slip_bps, commission_per_share=args.comm)
    port = Portfolio(initial_cash=args.cash)

    res = run_backtest(bars, strategy=strat, portfolio=port, broker=broker)

    # Enrich metrics with trade stats and period returns (month)
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
            print(f"  {k:>13}: {v*100:.2f}%")

    # Trade stats
    if res.trades:
        print("Trade Stats:")
        def fmt_pct(x: float) -> str:
            return f"{x*100:.2f}%"
        print(f"  {'trades':>13}: {int(m.get('trade_trades', 0))}")
        print(f"  {'win_rate':>13}: {fmt_pct(m.get('trade_win_rate', 0.0))}")
        print(f"  {'avg_win':>13}: {m.get('trade_avg_win', 0.0):.2f}")
        print(f"  {'avg_loss':>13}: {m.get('trade_avg_loss', 0.0):.2f}")
        print(f"  {'profit_factor':>13}: {m.get('trade_profit_factor', 0.0):.2f}")
        print(f"  {'avg_ret':>13}: {fmt_pct(m.get('trade_avg_ret', 0.0))}")
        print(f"  {'avg_hold_days':>13}: {m.get('trade_avg_hold_days', 0.0):.2f}")
        print(f"  {'monthly_count':>13}: {int(m.get('monthly_count', 0))}")

    # Show last 5 equity points
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
