PyBT - 模块化事件驱动回测框架
================================

PyBT 是一个以事件总线为核心的 Python 回测框架，强调组件解耦和配置驱动。
当前代码已包含完整主链路：数据源 -> 策略 -> 组合 -> 风控 -> 执行 -> 绩效报告。

核心能力
--------
- 事件驱动引擎：`BacktestEngine` + 同步 FIFO `EventBus`，统一调度 `MarketEvent/SignalEvent/OrderEvent/FillEvent/MetricsEvent`。
- 数据源：`InMemoryBarFeed`、`LocalCSVBarFeed`（CSV/Parquet）、`RESTPollingFeed`、`WebSocketJSONFeed`、`ADataLiveFeed`。
- 策略：`MovingAverageCrossStrategy`（双均线）与 `UptrendBreakoutStrategy`（趋势突破）。
- 执行：`ImmediateExecutionHandler` 支持滑点、佣金、部分成交、行情陈旧保护、成交时机（`current_close`/`next_open`）。
- 风控：`MaxPositionRisk`、`BuyingPowerRisk`、`ConcentrationRisk`、`PriceBandRisk`。
- 绩效：`EquityCurveReporter`、`DetailedReporter`、`TradeLogReporter`（JSONL/SQLite）。
- 配置化装配：`load_engine_from_dict()` / `load_engine_from_json()` 将 JSON 配置直接装配为可运行引擎。

安装
----
```bash
python -m venv .venv
source .venv/bin/activate

pip install -e .[dev]
# 可选：数据处理（pandas）
pip install -e .[data]
# 可选：实时行情（adata/requests/websockets）
pip install -e .[realtime]
# 可选：HTTP API
pip install -e .[server]
# 可选：Telegram Bot
pip install -e .[app]
```

快速开始（代码装配）
--------------------
```python
from datetime import datetime, timedelta

from pybt import BacktestEngine, Bar, EngineConfig, configure_logging
from pybt.analytics import EquityCurveReporter
from pybt.data import InMemoryBarFeed
from pybt.execution import ImmediateExecutionHandler
from pybt.portfolio import NaivePortfolio
from pybt.risk import MaxPositionRisk
from pybt.strategies import MovingAverageCrossStrategy


def synthetic_bars(symbol: str, start: datetime, periods: int) -> list[Bar]:
    out: list[Bar] = []
    price = 100.0
    for i in range(periods):
        price += 0.5
        ts = start + timedelta(days=i)
        out.append(
            Bar(
                symbol=symbol,
                timestamp=ts,
                open=price - 0.2,
                high=price + 0.3,
                low=price - 0.3,
                close=price,
                volume=1000 + i,
                amount=price * (1000 + i),
            )
        )
    return out


start = datetime(2024, 1, 1)
bars = synthetic_bars("TEST", start, periods=40)

configure_logging("INFO", json_format=False)

engine = BacktestEngine(
    data_feed=InMemoryBarFeed(bars),
    strategies=[MovingAverageCrossStrategy(symbol="TEST", short_window=3, long_window=8)],
    portfolio=NaivePortfolio(lot_size=100, initial_cash=100_000.0),
    execution=ImmediateExecutionHandler(slippage=0.0, commission=0.0, fill_timing="next_open"),
    risk_managers=[MaxPositionRisk(limit=500)],
    reporters=[EquityCurveReporter(initial_cash=100_000.0)],
    config=EngineConfig(name="demo", start=start, end=bars[-1].timestamp),
)

engine.run()
```

配置驱动运行
------------
`pybt.configuration.loader` 当前支持以下组件类型：

- `data_feed.type`: `local_csv` / `local_file` / `inmemory` / `rest` / `websocket` / `adata`
- `strategies[].type`: `moving_average` / `uptrend` / `plugin`
- `portfolio.type`: `naive`
- `execution.type`: `immediate`
- `risk[].type`: `max_position` / `buying_power` / `concentration` / `price_band`
- `reporters[].type`: `equity` / `detailed` / `tradelog`

最小配置示例：

```json
{
  "name": "cfg-demo",
  "data_feed": {
    "type": "local_csv",
    "path": "./data/AAA/Bar.csv",
    "symbol": "AAA"
  },
  "strategies": [
    {
      "type": "moving_average",
      "symbol": "AAA",
      "short_window": 5,
      "long_window": 20
    }
  ],
  "portfolio": {
    "type": "naive",
    "lot_size": 100,
    "initial_cash": 100000
  },
  "execution": {
    "type": "immediate",
    "slippage": 0.0,
    "commission": 0.0,
    "fill_timing": "next_open"
  },
  "risk": [
    {
      "type": "max_position",
      "limit": 500
    }
  ],
  "reporters": [
    {
      "type": "equity"
    }
  ]
}
```

插件策略示例：

```json
{
  "type": "plugin",
  "class_path": "strategies.test_plugins.NoopPluginStrategy",
  "params": {
    "symbol": "AAA",
    "strategy_id": "smoke-plugin"
  }
}
```

```python
from pathlib import Path

from pybt import configure_logging, load_engine_from_json

configure_logging("INFO", json_format=False)
engine = load_engine_from_json(Path("./config.json"))
engine.run()
```

CLI
---
```bash
python -m pybt --config ./config.json --log-level INFO --json-logs
```

应用层入口（可选）
----------------
HTTP API（FastAPI）：
```bash
pip install -e .[server]
export PYBT_API_KEY=your_key
pybt-server
```

常用环境变量：
- `PYBT_SERVER_HOST`（默认 `127.0.0.1`）
- `PYBT_SERVER_PORT`（默认 `8765`）
- `PYBT_BASE_DIR`（默认 `~/.pybt`）
- `PYBT_MAX_CONCURRENT_RUNS`（默认 `4`）

Telegram Bot：
```bash
pip install -e .[app]
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_ADMIN_PASSWORD=your_password
export PYBT_API_KEY=your_key
export PYBT_SERVER_URL=http://127.0.0.1:8765
pybt-bot
```

端到端 Smoke 验证（本地）
----------------------
该脚本会自动启动本地 server、提交内存行情配置、触发策略运行，并通过 Telegram outbox 发送链路做一次完整联调（使用 mock sender，不依赖真实 Telegram 网络）。

```bash
python3.11 scripts/smoke_realtime_pipeline.py --timeout 40
```

可选：保留运行目录便于排查

```bash
python3.11 scripts/smoke_realtime_pipeline.py --timeout 40 --base-dir /tmp/pybt_smoke
```

项目结构
--------
- `pybt/core/`: 引擎、事件总线、事件模型、接口、基础类型。
- `pybt/data/`: 各类行情数据源与本地文件加载。
- `pybt/strategies/`: 示例策略实现。
- `pybt/portfolio/`: 组合实现（当前为 `NaivePortfolio`）。
- `pybt/execution/`: 执行器实现（当前为 `ImmediateExecutionHandler`）。
- `pybt/risk/`: 风控模块。
- `pybt/analytics/`: 绩效统计与交易日志。
- `pybt/configuration/`: 配置定义与引擎装配。
- `apps/server/`: FastAPI 服务（配置管理、运行管理、事件查询与流式推送）。
- `apps/telegram_bot/`: Telegram 交互层。
- `tests/`: PyTest 测试。

开发与验证
----------
```bash
pytest -q
black .
mypy pybt
```

注意事项
--------
- `execution.fill_timing="current_close"` 默认值更偏向教学/回放；若追求更现实的时序，建议使用 `next_open` 以降低未来函数偏差。
- `ADataLiveFeed` 依赖 `adata`，未安装时请避免使用 `data_feed.type="adata"`。
- 内置策略与组合/风控实现偏简化，生产环境建议扩展交易成本、容量约束与更严格的数据校验。
