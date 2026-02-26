# PyBT Telegram Bot 最小可运行手册（10 步）

适合第一次上手，目标是：**从 0 到跑起一个策略并收到事件推送**。

## 0. 前置

- 已安装项目依赖（至少 `.[server]` 和 `.[app]`）。
- 已准备：
  - `PYBT_API_KEY`
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_ADMIN_PASSWORD`

## 1) 初始化本地敏感配置

```bash
mkdir -p ~/.pybt
cp examples/user_env_config.jsonc ~/.pybt/config.jsonc
```

按需填写 `~/.pybt/config.jsonc` 中的 headers/token。

## 2) 启动 Server

```bash
export PYBT_API_KEY=your_key
export PYBT_BASE_DIR=$HOME/.pybt
pybt-server
```

## 3) 启动 Bot

```bash
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_ADMIN_PASSWORD=your_password
export PYBT_API_KEY=your_key
export PYBT_SERVER_URL=http://127.0.0.1:8765
export PYBT_BOT_ADVANCED=1
pybt-bot
```

## 4) 在 Telegram 私聊登录

```text
/login <password>
```

## 5) 创建草稿

```text
/draft_new 600000
```

## 6) 设置数据源（Sina API）

```text
/set_feed sina_marketdata symbol=600000 transport=api
```

## 7) 增加策略

```text
/add_strategy moving_average symbol=600000 short_window=5 long_window=20 strategy_id=mac debug_signal=true
```

## 8) 启动草稿运行

```text
/run_draft
```

## 9) 查看与订阅

```text
/runs running limit=5
/status <run_id>
/subscribe <run_id>
```

## 10) 停止运行

```text
/program_stop <run_id>
/unsubscribe <run_id>
/logout
```

---

## 最短命令串（可复制）

```text
/login <password>
/draft_new 600000
/set_feed sina_marketdata symbol=600000 transport=api
/add_strategy moving_average symbol=600000 short_window=5 long_window=20 strategy_id=mac debug_signal=true
/run_draft
/runs running limit=5
```
