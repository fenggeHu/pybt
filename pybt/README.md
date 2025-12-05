PyBT – 模块化事件驱动回测框架
================================

功能概览
--------
- 事件驱动：`BacktestEngine` + 同步 FIFO `EventBus` 串联数据源、策略、风控、执行、组合、绩效。
- 数据源：内存 Bar 流、CSV/Parquet 日线、本地 AData 实时行情，以及通用 REST/WebSocket 实时适配器（可选依赖）。
- 策略示例：移动均线金叉、上升趋势突破（仅做多/平仓）。
- 组合/风控/执行：极简组合（lot 固定仓位）、最大持仓/买力/集中度/价格带风控、即时成交（可配置滑点/佣金/部分成交/行情陈旧保护）。
- 绩效：权益曲线与详细交易/回撤报告。
- 日志：`pybt.configure_logging()` 提供快速日志初始化（支持 JSON 格式）。

安装与开发
-----------
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
# 可选依赖：pip install -e .[data]  # pandas
# 可选依赖：pip install -e .[realtime]  # adata（实时行情）
pytest -q
```

JSON 配置运行
--------------
```json
{
  "name": "cfg-demo",
  "data_feed": {"type": "local_csv", "path": "./data/AAA/Bar.csv", "symbol": "AAA"},
  "strategies": [{"type": "moving_average", "symbol": "AAA", "short_window": 5, "long_window": 20}],
  "portfolio": {"type": "naive", "lot_size": 100, "initial_cash": 100000},
  "execution": {"type": "immediate", "slippage": 0.01, "commission": 1.0},
  "risk": [{"type": "max_position", "limit": 500}],
  "reporters": [{"type": "equity", "initial_cash": 100000}]
}
```

```python
from pathlib import Path
from pybt import load_engine_from_json, configure_logging

configure_logging("INFO", json_format=False)
engine = load_engine_from_json(Path("./config.json"))
engine.run()
```

命令行运行
----------
```bash
python -m pybt --config ./config.json --log-level INFO --json-logs
```

快速开始
---------
```python
from datetime import datetime, timedelta
from pybt import BacktestEngine, Bar, EngineConfig
from pybt import configure_logging
from pybt.data import InMemoryBarFeed
from pybt.strategies import MovingAverageCrossStrategy
from pybt.portfolio import NaivePortfolio
from pybt.execution import ImmediateExecutionHandler
from pybt.risk import MaxPositionRisk
from pybt.analytics import EquityCurveReporter

def synthetic_bars(symbol: str, start: datetime, periods: int):
    price = 100.0
    for i in range(periods):
        price += 0.5
        ts = start + timedelta(days=i)
        yield Bar(symbol, ts, price - 0.2, price + 0.3, price - 0.3, price, 1000)

start = datetime(2024, 1, 1)
bars = list(synthetic_bars("TEST", start, 60))
configure_logging("INFO")
engine = BacktestEngine(
    data_feed=InMemoryBarFeed(bars),
    strategies=[MovingAverageCrossStrategy(symbol="TEST", short_window=3, long_window=8)],
    portfolio=NaivePortfolio(lot_size=100),
    execution=ImmediateExecutionHandler(slippage=0.01, commission=1.0),
    risk_managers=[MaxPositionRisk(limit=500)],
    reporters=[EquityCurveReporter(initial_cash=100_000.0)],
    config=EngineConfig(name="demo", start=start, end=bars[-1].timestamp),
)
engine.run()
```

项目结构
--------
- `core/`: 引擎、事件、事件总线、接口、基础模型与枚举。
- `data/`: 内存/CSV/Parquet/AData 数据源。
- `strategies/`: 示例策略（移动均线、上升突破）。
- `portfolio/`: 组合实现。
- `execution/`: 执行器实现。
- `risk/`: 风控模块。
- `analytics/`: 绩效与报告。
- `examples/`: 端到端示例脚本。

注意事项
--------
- AData 实时行情需要安装额外包 `adata`。
- 策略示例为教学用途，生产场景请根据需求扩展风控、执行和数据校验。
