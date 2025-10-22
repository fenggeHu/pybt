pybt - Minimal Quant Backtesting Skeleton

Features

- Single-symbol, event-lite backtester
- Multi-symbol backtester with per-symbol strategies
- CSV loader or synthetic data generator
- SMA/EMA indicators; SMA crossover strategy
- Donchian breakout example using stop orders
- Simulated broker with bps slippage and per-share commission
- Portfolio with mark-to-market equity; Sharpe, MDD, CAGR metrics
- Limit/Stop/Market orders; simple risk rules (max units, protective stop)
- Optional weight allocator (leverage clamp, lot rounding) + SMA weight strategy demo
- Trade ledger + stats; monthly/yearly returns; CSV/JSON export; config and logging

Quick start

- Run: python3 scripts/run_backtest.py --csv data/SPY_sample.csv --fast 10 --slow 30
- Or without a CSV, it will auto-generate synthetic data.
- Exports: add `--out-dir out` to dump `equity.csv`, `trades.csv`, `metrics.json`.
- Config: use `--config configs/example_single.json` to load defaults, CLI overrides.
- Logging: `--log DEBUG` for detailed fills.

Multi-symbol

- Prepare CSVs in `data/` like `AAPL.csv, MSFT.csv` (date,open,high,low,close,volume)
- SMA example: python3 scripts/run_backtest_multi.py --data-dir data --fast 10 --slow 30 --max-units 5
- Breakout example (stop orders): python3 scripts/run_breakout_multi.py --data-dir data --lookback 20 --qty 1
- You can also pass `--out-dir`, `--config`, `--log` here.
- Weight-based SMA trend (targets via allocator):
  python3 scripts/run_weighted_multi.py --data-dir data --fast 10 --slow 30 --long-weight 0.5 --max-leverage 1.0
  --allow-short --short-weight -0.5

Project layout

- pybt/data: Bar model and CSV loader
- pybt/data/feed.py: Simple multi-symbol event feed
- pybt/indicators: Basic SMA/EMA
- pybt/strategy: Strategy base and SMA crossover
- pybt/strategy/breakout.py: Donchian breakout using stop orders
- pybt/strategy/weight.py: SMA trend strategy that emits target weights
- pybt/execution: SimBroker and Fill
- pybt/execution/order.py: Order model (market/limit/stop)
- pybt/portfolio: Portfolio tracking cash, position, equity
- pybt/portfolio/multi.py: Multi-symbol portfolio
- pybt/engine: Backtest runner and result
- pybt/engine/multi.py: Multi-symbol backtester
- pybt/risk/metrics.py: Performance metrics
- pybt/risk/rules.py: Simple risk manager (caps, protective stop)
- pybt/allocation/weights.py: Weight allocator converting weights→units with leverage clamp

Notes

- Standard library only. You can plug pandas later if desired.
- Prices filled at bar.open; PnL marked at bar.close.
- Limit/Stop fills use OHLC logic with gap handling; simplifications apply.
