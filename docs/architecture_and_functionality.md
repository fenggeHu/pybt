# PyBT 系统架构与功能分析

本文档基于当前仓库实现，对 PyBT 的系统分层、关键模块职责、核心运行链路和主要风险点进行结构化说明。

## 1. 系统定位

PyBT 是一个以事件总线为核心的配置驱动回测/准实时执行系统。整体由三层组成：

- 核心引擎层：`pybt/`，负责领域模型、引擎调度与组件接口。
- 应用编排层：`apps/server/`，负责配置管理、运行管理、事件查询与推送。
- 交互通知层：`apps/telegram_bot/`，负责用户交互与消息投递。

另有 `stock-mcp/` 子项目，提供 A 股数据 MCP 服务，工程上与主链路相对独立。

## 2. 架构分层

### 2.1 核心引擎层（Domain Kernel）

关键文件：

- `pybt/core/engine.py`
- `pybt/core/event_bus.py`
- `pybt/core/events.py`
- `pybt/core/interfaces.py`

设计要点：

- 同步 FIFO 事件总线，保证可预测的处理顺序。
- `BacktestEngine` 统一调度 `MarketEvent -> SignalEvent -> OrderEvent -> FillEvent -> MetricsEvent`。
- 组件通过统一接口接入（DataFeed/Strategy/Portfolio/Execution/Risk/Reporter），实现低耦合替换。

### 2.2 配置装配层（Configuration Assembly）

关键文件：

- `pybt/configuration/loader.py`
- `pybt/configuration/definitions.py`

设计要点：

- `load_engine_from_dict/load_engine_from_json` 将 JSON 配置装配为可运行引擎。
- 支持数据源、策略（含 plugin）、组合、执行、风控、报告器的类型化构建。
- `definitions.py` 提供可枚举组件定义，适合给 UI/文档生成消费。

### 2.3 应用编排层（Server Orchestration）

关键文件：

- `apps/server/app.py`
- `apps/server/run_manager.py`
- `apps/server/worker.py`

设计要点：

- FastAPI 暴露配置、运行、事件、摘要等 API。
- `RunManager` 以多进程隔离 run，主进程通过队列聚合子进程事件。
- worker 进程中装配并运行引擎，将事件序列化后回传。

### 2.4 交互通知层（Telegram + Outbox）

关键文件：

- `apps/telegram_bot/telegram_bot.py`
- `pybt/live/bridge.py`
- `pybt/live/contracts.py`
- `pybt/live/notify/outbox.py`
- `pybt/live/notify/notifier.py`

设计要点：

- Bot 调用 server API 发起运行、查看状态、订阅事件流。
- worker 将 `SignalEvent` 桥接为 `NotificationIntentEvent`，形成可投递的统一消息契约。
- Outbox 基于 SQLite，支持去重、重试、死信，保障“至少一次”投递语义。

## 3. 功能矩阵

### 3.1 数据采集

- 支持 `inmemory`、`local_csv/local_file`、`rest`、`websocket`、`adata`、`eastmoney_sse`。
- 本地回测与准实时行情通过同一事件模型接入，降低策略迁移成本。

### 3.2 策略与交易执行

- 内置 `moving_average`、`uptrend`，并支持 plugin class 动态加载。
- 执行器支持滑点、佣金、部分成交、行情新鲜度约束和成交时机（`current_close/next_open`）。
- 风控链支持最大仓位、买力、集中度、价格带等约束。

### 3.3 分析与审计

- 报告器支持权益曲线、详细报告、交易日志（JSONL/SQLite）。
- 可通过 server 的 run summary 查询回测结果，支持事件回放式排查。

### 3.4 运行与运维

- server 支持多 run 并发上限控制。
- telegram bot 支持用户鉴权、配置提交、run 启停、订阅/取消订阅。
- 脚本支持 server+bot 一键启动、健康检查、优雅停止。

## 4. 三条关键端到端链路

### 4.1 CLI 回测链路

1. `python -m pybt --config <path>`
2. 读取 JSON 并装配 `BacktestEngine`
3. 引擎循环驱动并产出 metrics

### 4.2 Server 运行链路

1. 客户端 `POST /runs`
2. `RunManager.start` 创建 run 进程和事件队列
3. worker 执行引擎并发送事件
4. 主进程缓存事件，API/WS 提供消费

### 4.3 Telegram 订阅链路

1. 用户 `/subscribe <run_id>`
2. bot 优先使用 WS（失败回退轮询）拉取事件
3. 事件入 outbox 去重/重试
4. notifier 投递到 Telegram chat

## 5. 主要架构优势

- 领域内核和集成层边界清晰，扩展点集中在配置与接口实现。
- 事件驱动模型统一了回测与准实时处理语义。
- Outbox 机制降低通知丢失概率，便于审计与补偿。

## 6. 当前风险与改进建议

### 6.1 风险点

- `RunManager` 状态以内存为主，服务重启后 run 元数据与事件窗口不可恢复。
- `docker-compose.yml` 引用了当前仓库未出现的 `backend/frontend` 路径，存在运维误导风险。
- 事件总线是单线程同步分发，高频场景的吞吐与背压能力受限。

### 6.2 建议

- 将 run 元数据与事件索引落盘（SQLite/PostgreSQL），提高服务重启恢复能力。
- 清理或重写过期 compose 文件，避免错误部署路径。
- 在高频场景引入分层队列与采样策略（指标、通知侧先行），降低主循环压力。

## 7. 数据流程图（draw.io）

- 文件：`docs/diagrams/pybt-data-flow.drawio`
- 使用 diagrams.net 打开即可编辑。
