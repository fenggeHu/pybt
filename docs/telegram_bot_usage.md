# PyBT Telegram Bot 使用文档

本文档面向运维和策略开发同学，描述如何通过 Telegram Bot 完成运行编排、插件管理、草稿配置和调试排障。首次上手建议先看 `docs/telegram_bot_minimal_runbook.md`。

## 1. 启动准备

### 1.1 启动 Server

```bash
export PYBT_API_KEY=your_key
export PYBT_BASE_DIR=$HOME/.pybt
# 可选：指定插件注册表文件
export PYBT_PLUGIN_REGISTRY=/path/to/plugins/plugin.jsonc

pybt-server
```

关键环境变量：

- `PYBT_SERVER_HOST`（默认 `127.0.0.1`）
- `PYBT_SERVER_PORT`（默认 `8765`）
- `PYBT_API_KEY`（必填）
- `PYBT_BASE_DIR`（默认 `~/.pybt`）
- `PYBT_MAX_CONCURRENT_RUNS`（默认 `4`）
- `PYBT_PLUGIN_REGISTRY`（可选，不设置时自动发现 `plugins/plugin.jsonc`）

### 1.2 启动 Bot

```bash
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_ADMIN_PASSWORD=your_password
export PYBT_API_KEY=your_key
export PYBT_SERVER_URL=http://127.0.0.1:8765

pybt-bot
```

### 1.3 用户敏感配置（推荐）

- 默认文件：`~/.pybt/config.jsonc`
- `pybt` / `pybt-server` / `pybt-bot` 启动时会自动创建该文件模板。
- 用于存放 token/cookie/header 等敏感信息，避免写入仓库配置。

可先复制模板并填写：

```bash
mkdir -p ~/.pybt
cp examples/user_env_config.jsonc ~/.pybt/config.jsonc
```

说明：

- `configs/data_feeds/sina_hq_api_live.jsonc` 默认引用 `~/.pybt/config.jsonc#secrets.sina.headers`
- `configs/data_feeds/eastmoney_600000_sse.jsonc` 默认引用 `~/.pybt/config.jsonc#secrets.eastmoney.{token,headers,snapshot_headers}`

建议至少保留以下结构（按需填写）：

```jsonc
{
  "secrets": {
    "eastmoney": {
      "token": "",
      "headers": {},
      "snapshot_headers": {}
    },
    "sina": {
      "headers": {}
    }
  }
}
```

可用以下命令快速校验引用是否可解析：

```bash
python -m pybt --config ./configs/profiles/sina_hq_api_live.jsonc --self-check
python -m pybt --config ./configs/profiles/eastmoney_sse_prod.jsonc --self-check
```

## 2. 登录与访问控制

- 私聊中先执行：`/login <password>`
- 退出登录：`/logout`
- 命令帮助：`/help` 或 `/start`
- 菜单入口：`/menu`

说明：

- 未登录状态下，编排/管理类命令会被拒绝。
- 登录态会落在 `PYBT_BASE_DIR/telegram_auth.json`。

## 3. 命令总览

### 3.1 运行编排（Run / Program）

- `/runs [state=<all|running|starting|completed|failed|stopped>|<state>] [limit=20]`
- `/status <run_id>`
- `/summary <run_id>`
- `/program_start <config_name|draft>`
- `/program_stop <run_id>`
- `/stop <run_id>`（兼容命令）
- `/run_compare <left_run_id> <right_run_id>`
- `/run_signals <run_id> [strategy_id=...] [symbol=...] [since_seq=0] [limit=20] [include_debug=true|false]`
- `/subscribe <run_id>`
- `/unsubscribe <run_id>`

### 3.2 配置与草稿

- `/configs`
- `/definitions [data_feed|strategy|portfolio|execution|risk|reporter]`
- `/run`（进入一次性“下一条 JSON/文件即启动”模式）
- `/draft_new [symbol]`
- `/draft_show`
- `/set_feed <plugin> key=value ...` 或 JSON
- `/add_strategy <plugin> key=value ...` 或 JSON
- `/set_strategy <index> <plugin> key=value ...` 或 JSON
- `/del_strategy <index>`
- `/list_strategy`
- `/strategy on/off <index|strategy_id|all>`
- `/save_draft <name.json> [force]`
- `/run_draft`

### 3.3 插件管理

- `/plugins [kind=<kind>|<kind>] [enabled=true|false|on|off]`
- `/plugin_load <plugin_name>`
- `/plugin_unload <plugin_name>`
- `/program_help`（同 `/plugin_help`）
- `/plugin_help`

## 4. 运行编排详解

### 4.1 `/runs` 过滤规则

支持两种写法：

- 显式：`/runs state=running limit=10`
- 简写：`/runs running`

状态别名：

- `start` -> `starting`
- `run` -> `running`
- `done` / `complete` -> `completed`
- `fail` -> `failed`
- `stop` -> `stopped`
- `all` -> 不过滤

默认 `limit=20`，上限 `50`。

### 4.2 `/program_start` 用法

- `/program_start draft`：直接运行当前用户草稿
- `/program_start xxx`：自动补全为 `xxx.json` 后按保存配置启动

### 4.3 `/run_compare` 用法

```text
/run_compare run_a run_b
```

返回两个运行在事件计数和 summary 数值项上的差异，适合策略参数 AB 对比。

### 4.4 `/run_signals` 用法

```text
/run_signals run_id strategy_id=mac symbol=600000 include_debug=true limit=50
```

也支持快捷调试开关：

- `debug` 等价于 `include_debug=true`
- `nodebug` 等价于 `include_debug=false`

## 5. 插件管理详解

### 5.1 查看插件

```text
/plugins
/plugins strategy
/plugins data_feed on
/plugins kind=data_feed enabled=false
```

### 5.2 启用/停用插件

```text
/plugin_load sina_marketdata
/plugin_unload eastmoney_marketdata
```

说明：

- `load/unload` 会修改插件注册表中的 `enabled` 状态。
- 影响后续新启动 run；已在运行中的实例不受影响。
- 插件注册表写回采用“最小文本改动”并保留注释，且含并发写保护。

## 6. 菜单按钮用法

### 6.1 Runs 页面

按钮支持：

- `All / Running / Failed / Completed / Stopped / Refresh`

点进单个 run 后可执行：

- `Status / Summary / Stop / Subscribe / Unsubscribe`

### 6.2 Plugins 页面

按钮支持：

- `All / DataFeed / Strategy / ON / OFF / Refresh`

点进单个 plugin 后可执行：

- `Load` 或 `Unload`

## 7. 草稿推荐工作流

```text
/draft_new 600000
/set_feed eastmoney_marketdata symbol=600000 transport=sse
/add_strategy moving_average symbol=600000 short_window=5 long_window=20 strategy_id=mac debug_signal=true
/list_strategy
/run_draft
```

策略启停：

```text
/strategy off mac
/strategy on 0
/strategy off all
```

## 8. 订阅与告警

执行 `/subscribe <run_id>` 后，Bot 会推送：

- `FillEvent`
- `MetricsEvent`
- `NotificationIntentEvent`
- `DataSourceStatusEvent`（仅 `status=error` 推送，减少恢复类噪音）

若 websocket 依赖缺失，会自动回退到轮询模式。

## 9. 常见问题

### 9.1 `/program_start xxx` 报配置不存在

先执行 `/configs` 检查配置名，或先 `/save_draft xxx.json`。

### 9.2 插件已 unload，为何运行还在继续

插件启停只影响新 run，不会中断已启动 run。

### 9.3 为什么信号没触发

在策略参数中开启 `debug_signal=true`，再用 `/run_signals ... include_debug=true` 查看调试事件。
