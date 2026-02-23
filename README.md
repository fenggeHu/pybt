PyBT - 模块化事件驱动回测框架
================================

PyBT 是一个以事件总线为核心的 Python 回测框架，强调组件解耦和配置驱动。
当前代码已包含完整主链路：数据源 -> 策略 -> 组合 -> 风控 -> 执行 -> 绩效报告。

核心能力
--------
- 事件驱动引擎：`BacktestEngine` + 同步 FIFO `EventBus`，统一调度 `MarketEvent/SignalEvent/OrderEvent/FillEvent/MetricsEvent`。
- 数据源：`InMemoryBarFeed`、`LocalCSVBarFeed`（CSV/Parquet）、`RESTPollingFeed`、`WebSocketJSONFeed`、`ADataLiveFeed`、`EastmoneySSEFeed`、`ComposableQuoteFeed`（插件链）。
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

生产运行建议
-----------
生产环境建议统一走**配置驱动**（server + telegram-bot + JSON/JSONC 配置），避免在代码中写死策略参数和行情源。
推荐直接使用下文的一键启停脚本和 A 股实盘配置。

配置驱动运行
------------
`load_engine_from_json()` 支持：
- `.json` / `.jsonc`（允许 `//`、`/* */` 注释与尾逗号）；
- 局部 `$ref` 组合（可把数据源、策略、执行、风控拆成独立文件再组装）。

推荐目录规划：
- `configs/data_feeds/*.jsonc`
- `configs/strategies/*.jsonc`
- `configs/portfolios/*.jsonc`
- `configs/executions/*.jsonc`
- `configs/risk/*.jsonc`
- `configs/reporters/*.jsonc`
- `configs/profiles/*.jsonc`（组合入口，可直接用于 `--run-config`）

装配规则（新）：

- 所有核心节点统一使用 `plugin + params` 形式。
- 插件元数据来自 `plugins/plugin.jsonc`（可通过 `plugin_registry` 指定）。
- 每个插件只声明一个 `kind`（`data_feed` / `strategy` / `portfolio` / `execution` / `risk` / `reporter`）。
- 可选 `strict_params`：开启后会拒绝未声明参数（减少拼写错误导致的静默配置问题）。

若启用了 server，可通过 `GET /definitions`（需 `X-API-Key`）获取完整组件定义与参数元数据，便于 UI 或 Bot 做自动提示。

最简实时行情示例（Eastmoney 插件）：

```json
{
  "plugin": "eastmoney_marketdata",
  "params": {
    "symbol": "600000",
    "transport": "sse"
  }
}
```

最小配置示例：

```json
{
  "name": "ashare-live-prod",
  "plugin_registry": "plugins/plugin.jsonc",
  "data_feed": {
    "plugin": "local_csv_feed",
    "params": {
      "path": "./data/AAA/Bar.csv",
      "symbol": "AAA"
    }
  },
  "strategies": [
    {
      "plugin": "moving_average",
      "params": {
        "symbol": "AAA",
        "short_window": 5,
        "long_window": 20
      }
    }
  ],
  "portfolio": {
    "plugin": "naive_portfolio",
    "params": {
      "lot_size": 100,
      "initial_cash": 100000
    }
  },
  "execution": {
    "plugin": "immediate_execution",
    "params": {
      "slippage": 0.0,
      "commission": 0.0,
      "fill_timing": "next_open"
    }
  },
  "risk": [
    {
      "plugin": "max_position_risk",
      "params": {
        "limit": 500
      }
    }
  ],
  "reporters": [
    {
      "plugin": "equity_reporter"
    }
  ]
}
```

自定义策略插件示例：

```json
{
  "plugin": "my_live_strategy",
  "params": {
    "symbol": "AAA",
    "strategy_id": "my-live"
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

先做自检（推荐）：

```bash
python -m pybt --config ./config.json --self-check
```

快速体验（可直接复制）：

```bash
# Eastmoney SSE
python -m pybt --config ./examples/profiles/eastmoney_sse_quickstart.jsonc --self-check
python -m pybt --config ./examples/profiles/eastmoney_sse_quickstart.jsonc --log-level INFO

# Sina API
python -m pybt --config ./examples/profiles/sina_api_quickstart.jsonc --self-check
python -m pybt --config ./examples/profiles/sina_api_quickstart.jsonc --log-level INFO
```

或使用一键自检脚本：

```bash
bash scripts/check_config.sh
bash scripts/check_config.sh ./examples/profiles/sina_api_quickstart.jsonc
```

应用层入口（可选）
----------------
HTTP API（FastAPI）：
```bash
pip install -e .[server]
export PYBT_API_KEY=your_key
pybt-server
```

平台调试/观测接口（需 `X-API-Key`）：
- `GET /runs/{run_id}/events`：按序查询事件。
- `GET /runs/{run_id}/signals?include_debug=true`：查询策略信号与调试事件（支持 `strategy_id`、`symbol`、`since_seq`、`limit` 过滤）。
- `GET /runs/{run_id}/compare/{other_run_id}`：比较两个运行，返回 `event_count_delta` 与数值类 `summary_delta`。
- `GET /runs/{run_id}/stream`（WebSocket）：实时推送事件；数据源异常/恢复会以 `DataSourceStatusEvent` 进入事件流。
- `GET /plugins`：列出插件及启用状态（支持 `kind`、`enabled` 过滤）。
- `POST /plugins/{name}/load`：启用插件。
- `POST /plugins/{name}/unload`：停用插件。

错误响应约定：
- 所有错误响应返回 `{"ok": false, "error": {...}}`。
- `error` 至少包含 `code`、`message`、`request_id`，并可能包含 `hint`、`details`。
- 响应头同时携带 `X-Request-ID`，便于跨 server/bot/日志排障。

常用环境变量：
- `PYBT_SERVER_HOST`（默认 `127.0.0.1`）
- `PYBT_SERVER_PORT`（默认 `8765`）
- `PYBT_BASE_DIR`（默认 `~/.pybt`）
- `PYBT_MAX_CONCURRENT_RUNS`（默认 `4`）
- `PYBT_PLUGIN_REGISTRY`（可选，默认自动发现 `plugins/plugin.jsonc`）

Telegram Bot：
```bash
pip install -e .[app]
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_ADMIN_PASSWORD=your_password
export PYBT_API_KEY=your_key
export PYBT_SERVER_URL=http://127.0.0.1:8765
pybt-bot
```

Telegram 命令化配置（数据源/策略）：
- `/definitions [data_feed|strategy|portfolio|execution|risk|reporter]`：查看支持的组件类型。
- `/draft_new [symbol]`：创建/重置当前草稿配置（按用户隔离）。
- `/set_feed <plugin> key=value...` 或 `/set_feed {"plugin":"...","params":{...}}`：设置数据源。
- `/add_strategy <plugin> key=value...`：新增策略。
- `/set_strategy <index> <plugin> key=value...`：替换某条策略。
- `/del_strategy <index>`：删除某条策略。
- `/list_strategy`：列出草稿里的策略及 ON/OFF 状态。
- `/strategy on/off <index|strategy_id|all>`：启用/停用策略。
- `/draft_show`：查看当前草稿 JSON。
- `/save_draft <name.json> [force]`：保存到 server 配置中心。
- `/run_draft`：直接以内联配置启动运行（无需先保存）。
- `/runs [state=<all|running|starting|completed|failed|stopped>|<state>] [limit=20]`：查看运行列表（支持状态过滤）。
- `Runs` 按钮页支持 `All/Running/Failed/Completed/Stopped/Refresh` 快捷过滤。
- `/program_start <config_name|draft>`：启动程序（配置名或当前 draft）。
- `/program_stop <run_id>`：停止程序。
- `/plugins [kind=<kind>|<kind>] [enabled=true|false|on|off]`：查看插件状态。
- `/plugin_load <plugin_name>`：加载（启用）插件。
- `/plugin_unload <plugin_name>`：卸载（停用）插件。
- `/program_help`：程序/插件相关命令帮助（同 `/plugin_help`）。
- `/plugin_help`：查看上述命令用法。
- `/run_compare <left_run_id> <right_run_id>`：比较两次运行（事件计数差异 + summary 数值差异）。
- `/run_signals <run_id> [strategy_id=...] [symbol=...] [since_seq=0] [limit=20] [include_debug=true|false]`：查看信号与策略调试事件。

策略调试参数（`strategies[].params`）：
- `moving_average` / `uptrend` 支持 `debug_signal=true`，会额外发出 `StrategyDebugEvent`，用于排查“为什么这根K线没有出信号”。

行情源稳定性参数（`data_feed.params`）：
- `source_failure_threshold`：单个 source 连续失败多少次后进入冷却（默认 `2`）。
- `source_cooldown_seconds`：冷却秒数（默认 `2.0`）。
- `emit_source_status`：是否发出数据源状态事件（默认 `true`）。

一键启动（生产链路）
------------------
脚本会启动 server + telegram-bot，并可选自动提交配置后直接开跑。

启动（后台）：

```bash
export PYBT_API_KEY=your_key
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_ADMIN_PASSWORD=your_password
export PYBT_BASE_DIR=$HOME/.pybt

bash scripts/start_realtime_system.sh --detach --run-config ./configs/profiles/ashare_live_prod.jsonc
```

A股生产推荐（直接用生产配置）：

```bash
export PYBT_API_KEY=your_key
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_ADMIN_PASSWORD=your_password
export PYBT_BASE_DIR=$HOME/.pybt

bash scripts/start_ashare_prod.sh
```

如需指定你自己的配置文件：

```bash
bash scripts/start_ashare_prod.sh ./configs/your_ashare_live.json
```

启动（前台，便于观察日志）：

```bash
bash scripts/start_realtime_system.sh --run-config ./configs/profiles/ashare_live_prod.jsonc
```

停止（根据 pid 文件优雅退出）：

```bash
bash scripts/stop_realtime_system.sh
```

仅检查环境变量与运行参数：

```bash
bash scripts/start_realtime_system.sh --check
```

生产配置文件（推荐 profile JSONC）：
- `configs/profiles/ashare_live_prod.jsonc`
- `configs/profiles/eastmoney_sse_prod.jsonc`
- `configs/profiles/sina_hq_api_live.jsonc`
- `configs/` 目录仅保留生产级配置。

快速体验配置：
- `examples/profiles/eastmoney_sse_quickstart.jsonc`
- `examples/profiles/sina_api_quickstart.jsonc`

连通性自检配置（一次拉取后自动退出）：
- `examples/profiles/eastmoney_sse_live_verify_once.jsonc`
- `examples/profiles/sina_hq_api_live_verify_once.jsonc`

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

架构文档
--------
- `docs/architecture_and_functionality.md`: 项目系统架构与功能分析。
- `docs/telegram_bot_usage.md`: Telegram Bot 运行编排与插件管理使用说明。
- `docs/telegram_bot_quickref.md`: Telegram Bot 一页速查（值守/排障常用命令）。
- `docs/diagrams/pybt-data-flow.drawio`: 可编辑的数据流程图（draw.io/diagrams.net）。

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
- `adata_live_feed` 插件依赖 `adata`，未安装时请避免启用该插件。
- `eastmoney_marketdata` 插件基于网页 SSE/API 通道，可能受网站风控策略、连接节流和参数变化影响，生产上建议准备备用行情源和告警。
- 切换供应商时，建议只替换 `data_feed.plugin`（如 `eastmoney_marketdata` / `sina_marketdata`）并复用相同策略配置。
- 内置策略与组合/风控实现偏简化，生产环境建议扩展交易成本、容量约束与更严格的数据校验。
