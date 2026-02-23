# PyBT Telegram Bot Quick Reference

一页速查，适合日常值守与快速操作。详细说明见 `docs/telegram_bot_usage.md`。

## 1) 启动

```bash
# server
export PYBT_API_KEY=your_key
export PYBT_BASE_DIR=$HOME/.pybt
pybt-server

# bot
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_ADMIN_PASSWORD=your_password
export PYBT_API_KEY=your_key
export PYBT_SERVER_URL=http://127.0.0.1:8765
pybt-bot
```

## 2) 登录

- `/login <password>`
- `/logout`
- `/help`

## 3) 运行编排

- `/runs [state=<all|running|starting|completed|failed|stopped>|<state>] [limit=20]`
- `/status <run_id>`
- `/summary <run_id>`
- `/program_start <config_name|draft>`
- `/program_stop <run_id>`
- `/run_compare <left_run_id> <right_run_id>`
- `/run_signals <run_id> [strategy_id=...] [symbol=...] [since_seq=0] [limit=20] [include_debug=true|false]`
- `/subscribe <run_id>`
- `/unsubscribe <run_id>`

状态别名：`run/start/done/fail/stop/all`
    `1`qe5t 

# asdtfyuiop[]'\
# 4) 草稿配置

- `/draft_new [symbol]`
- `/set_feed <plugin> key=value...`
- `/add_strategy <plugin> key=value...`
- `/set_strategy <index> <plugin> key=value...`
- `/del_strategy <index>`
- `/list_strategy`
- `/strategy on/off <index|strategy_id|all>`
- `/draft_show`
- `/save_draft <name.json> [force]`
- `/run_draft`

## 5) 插件管理

- `/plugins [kind=<kind>|<kind>] [enabled=true|false|on|off]`
- `/plugin_load <plugin_name>`
- `/plugin_unload <plugin_name>`
- `/program_help`（同 `/plugin_help`）

## 6) 常用排障

- 看运行列表：`/runs running limit=10`
- 看失败运行：`/runs failed limit=20`
- 对比两次运行：`/run_compare run_a run_b`
- 看策略调试：`/run_signals run_id include_debug=true limit=50`
- 订阅运行告警：`/subscribe run_id`

## 7) 备注

- 插件 `load/unload` 影响后续新 run，不会中断已在运行中的 run。
- `DataSourceStatusEvent` 仅 `status=error` 会推送告警消息（减少噪音）。
