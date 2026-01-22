from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import httpx

# Telegram is an optional dependency. We import it at runtime in main() so that
# `import pybt` and `pytest` work without the app extras installed.


def _utc_stamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        # Support ```json ... ``` and ``` ... ```.
        text = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    return text.strip()


def _parse_json(text: str) -> dict[str, Any]:
    raw = json.loads(_strip_json_fence(text))
    if not isinstance(raw, dict):
        raise ValueError("Config JSON must be an object")
    return raw


def _fmt_code(text: str) -> str:
    return f"<pre><code>{text}</code></pre>"


@dataclass
class BotState:
    api_base: str
    api_key: str
    allowed_user_ids: set[int]
    pending_run: set[int]
    subscriptions: dict[tuple[int, str], asyncio.Task]


async def _api(
    client: httpx.AsyncClient,
    state: BotState,
    method: str,
    path: str,
    json_body: Any = None,
) -> Any:
    url = state.api_base.rstrip("/") + path
    headers = {"X-API-Key": state.api_key}
    resp = await client.request(method, url, headers=headers, json=json_body, timeout=30)
    # server returns ok=false for HTTPException too; prefer status for flow.
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
    return resp.json()


def _check_auth(state: BotState, update: Any) -> bool:
    user = update.effective_user
    if user is None:
        return False
    return user.id in state.allowed_user_ids


async def cmd_help(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        return
    text = "\n".join(
        [
            "Commands:",
            "/configs - list configs", 
            "/run - upload config.json or paste JSON", 
            "/runs - list runs", 
            "/status <run_id>",
            "/summary <run_id>",
            "/stop <run_id>",
            "/subscribe <run_id>",
            "/unsubscribe <run_id>",
        ]
    )
    await update.message.reply_text(text)  # type: ignore[union-attr]


async def cmd_configs(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        return
    async with httpx.AsyncClient() as client:
        data = await _api(client, state, "GET", "/configs")
    items = data.get("configs", [])
    if not items:
        await update.message.reply_text("No configs")  # type: ignore[union-attr]
        return
    lines = ["Configs:"]
    for it in items[:50]:
        lines.append(f"- {it['name']} ({it['size_bytes']} bytes)")
    await update.message.reply_text("\n".join(lines))  # type: ignore[union-attr]


async def cmd_runs(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        return
    async with httpx.AsyncClient() as client:
        data = await _api(client, state, "GET", "/runs")
    runs = data.get("runs", [])
    if not runs:
        await update.message.reply_text("No runs")  # type: ignore[union-attr]
        return
    lines = ["Runs:"]
    for r in runs[:50]:
        lines.append(f"- {r['run_id']} state={r['state']} config={r['config_name']}")
    await update.message.reply_text("\n".join(lines))  # type: ignore[union-attr]


async def cmd_status(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /status <run_id>")  # type: ignore[union-attr]
        return
    run_id = context.args[0]
    async with httpx.AsyncClient() as client:
        data = await _api(client, state, "GET", f"/runs/{run_id}")
    await update.message.reply_text(json.dumps(data, ensure_ascii=False, indent=2))  # type: ignore[union-attr]


async def cmd_summary(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /summary <run_id>")  # type: ignore[union-attr]
        return
    run_id = context.args[0]
    async with httpx.AsyncClient() as client:
        data = await _api(client, state, "GET", f"/runs/{run_id}/summary")
    if not data.get("ok"):
        await update.message.reply_text(f"Summary not available: {data}")  # type: ignore[union-attr]
        return
    summary = data.get("summary", {})
    await update.message.reply_text(json.dumps(summary, ensure_ascii=False, indent=2))  # type: ignore[union-attr]


async def cmd_stop(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /stop <run_id>")  # type: ignore[union-attr]
        return
    run_id = context.args[0]
    async with httpx.AsyncClient() as client:
        await _api(client, state, "POST", f"/runs/{run_id}/stop")
    await update.message.reply_text(f"Stop requested: {run_id}")  # type: ignore[union-attr]


async def cmd_run(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        return
    msg = update.message
    if msg is None:
        return

    # Inline JSON: /run { ... }
    if context.args:
        raw = msg.text
        if raw is None:
            return
        json_part = raw.split(" ", 1)[1] if " " in raw else ""
        if not json_part.strip():
            await msg.reply_text("Paste JSON after /run or send config.json")
            return
        await _run_from_json_text(update, context, json_part)
        return

    # No args: enter pending mode (next message is JSON text or config.json upload).
    state.pending_run.add(update.effective_user.id)  # type: ignore[union-attr]
    await msg.reply_text("Send config.json (document) or paste JSON text.")


async def _run_from_json_text(update: Any, context: Any, text: str) -> None:
    state: BotState = context.bot_data["state"]
    msg = update.message
    if msg is None:
        return
    try:
        cfg = _parse_json(text)
    except Exception as exc:
        await msg.reply_text(f"Invalid JSON: {exc}")
        return

    config_name = f"tg_{update.effective_chat.id}_{_utc_stamp()}.json"  # type: ignore[union-attr]

    async with httpx.AsyncClient() as client:
        valid = await _api(client, state, "POST", "/configs/validate", {"config": cfg})
        if not valid.get("ok"):
            err = valid.get("error", {}).get("message", "validation failed")
            await msg.reply_text(f"Config validate failed: {err}")
            return
        await _api(client, state, "POST", f"/configs/{config_name}", cfg)
        run = await _api(client, state, "POST", "/runs", {"config_name": config_name})

    run_id = run.get("run_id")
    await msg.reply_text(
        "\n".join(
            [
                f"Started run: {run_id}",
                f"Config: {config_name}",
                f"/status {run_id}",
                f"/summary {run_id}",
                f"/stop {run_id}",
                f"/subscribe {run_id}",
            ]
        )
    )


async def on_document(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        return
    msg = update.message
    if msg is None:
        return
    doc = msg.document
    if doc is None:
        return

    # Accept only if user requested /run, or is in pending mode.
    caption = msg.caption or ""
    user_id = update.effective_user.id  # type: ignore[union-attr]
    if ("/run" not in caption) and (user_id not in state.pending_run):
        await msg.reply_text("Send /run first, or caption the file with /run")
        return

    if doc.file_size is not None and doc.file_size > 1_000_000:
        await msg.reply_text("Config too large (max 1MB)")
        return
    if doc.file_name is None or not doc.file_name.endswith(".json"):
        await msg.reply_text("Please upload a .json file")
        return

    file = await context.bot.get_file(doc.file_id)
    data = await file.download_as_bytearray()
    try:
        cfg = json.loads(bytes(data).decode("utf-8"))
        if not isinstance(cfg, dict):
            raise ValueError("Config JSON must be an object")
    except Exception as exc:
        await msg.reply_text(f"Invalid JSON file: {exc}")
        return

    # Clear pending state.
    state.pending_run.discard(user_id)
    config_name = f"tg_{update.effective_chat.id}_{_utc_stamp()}.json"  # type: ignore[union-attr]

    async with httpx.AsyncClient() as client:
        valid = await _api(client, state, "POST", "/configs/validate", {"config": cfg})
        if not valid.get("ok"):
            err = valid.get("error", {}).get("message", "validation failed")
            await msg.reply_text(f"Config validate failed: {err}")
            return
        await _api(client, state, "POST", f"/configs/{config_name}", cfg)
        run = await _api(client, state, "POST", "/runs", {"config_name": config_name})
    run_id = run.get("run_id")
    await msg.reply_text(f"Started run: {run_id}\n/subscribe {run_id}")


async def on_text(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        return
    msg = update.message
    if msg is None or msg.text is None:
        return
    user_id = update.effective_user.id  # type: ignore[union-attr]
    if user_id not in state.pending_run:
        return
    # Treat next text message as JSON config.
    state.pending_run.discard(user_id)
    await _run_from_json_text(update, context, msg.text)


def _format_event(ev: dict[str, Any]) -> Optional[str]:
    et = ev.get("event_type")
    data = ev.get("data", {})
    if et == "FillEvent":
        symbol = data.get("symbol")
        qty = data.get("quantity")
        price = data.get("fill_price")
        commission = data.get("commission")
        return f"FILL {symbol} qty={qty} price={price} commission={commission}"
    if et == "MetricsEvent":
        payload = data.get("payload", {})
        keys = ["equity", "cash", "max_drawdown", "total_trades"]
        parts = [f"{k}={payload.get(k)}" for k in keys if k in payload]
        return "METRICS " + " ".join(parts)
    return None


async def cmd_subscribe(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        return
    msg = update.message
    if msg is None:
        return
    if not context.args:
        await msg.reply_text("Usage: /subscribe <run_id>")
        return
    run_id = context.args[0]
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    key = (chat_id, run_id)
    if key in state.subscriptions:
        await msg.reply_text("Already subscribed")
        return

    async def stream_loop() -> None:
        # Prefer WebSocket streaming; fall back to HTTP polling.
        ws_url = state.api_base.rstrip("/")
        if ws_url.startswith("https://"):
            ws_url = "wss://" + ws_url[len("https://") :]
        elif ws_url.startswith("http://"):
            ws_url = "ws://" + ws_url[len("http://") :]
        ws_url = f"{ws_url}/runs/{run_id}/stream?types=FillEvent,MetricsEvent"

        try:
            import importlib

            websockets = importlib.import_module("websockets")
        except Exception:
            websockets = None

        if websockets is None:
            await context.bot.send_message(
                chat_id=chat_id,
                text="websockets not installed; falling back to polling",
            )
            await _poll_events_loop(context, state, chat_id, run_id)
            return

        backoff = 0.5
        while True:
            try:
                async with websockets.connect(
                    ws_url,
                    **_ws_headers_kwargs(websockets, state.api_key),
                    ping_interval=20,
                    ping_timeout=20,
                ) as ws:
                    backoff = 0.5
                    async for raw in ws:
                        if isinstance(raw, (bytes, bytearray)):
                            raw = raw.decode("utf-8")
                        msg = json.loads(raw)
                        if msg.get("kind") == "events":
                            for ev in msg.get("events", []):
                                text = _format_event(ev)
                                if text:
                                    await context.bot.send_message(chat_id=chat_id, text=text)
                        # heartbeat: ignore
            except asyncio.CancelledError:
                return
            except Exception:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 10.0)

    task = asyncio.create_task(stream_loop())
    state.subscriptions[key] = task
    await msg.reply_text(f"Subscribed: {run_id}")


def _ws_headers_kwargs(websockets_mod: Any, api_key: str) -> dict[str, Any]:
    """Build header kwargs compatible with multiple websockets versions."""

    connect = getattr(websockets_mod, "connect", None)
    if connect is None:
        return {}
    try:
        params = inspect.signature(connect).parameters
    except Exception:
        return {"extra_headers": {"X-API-Key": api_key}}
    if "additional_headers" in params:
        return {"additional_headers": {"X-API-Key": api_key}}
    if "extra_headers" in params:
        return {"extra_headers": {"X-API-Key": api_key}}
    return {}


async def _poll_events_loop(context: Any, state: BotState, chat_id: int, run_id: str) -> None:
    since = 0
    async with httpx.AsyncClient() as client:
        while True:
            data = await _api(
                client,
                state,
                "GET",
                f"/runs/{run_id}/events?since_seq={since}&limit=200",
            )
            events = data.get("events", [])
            for ev in events:
                text = _format_event(ev)
                if text:
                    await context.bot.send_message(chat_id=chat_id, text=text)
                since = max(since, int(ev.get("seq", since)))
            since = max(since, int(data.get("last_seq", since)))
            await asyncio.sleep(1.0)


async def cmd_unsubscribe(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        return
    msg = update.message
    if msg is None:
        return
    if not context.args:
        await msg.reply_text("Usage: /unsubscribe <run_id>")
        return
    run_id = context.args[0]
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    key = (chat_id, run_id)
    task = state.subscriptions.pop(key, None)
    if task is None:
        await msg.reply_text("Not subscribed")
        return
    task.cancel()
    await msg.reply_text(f"Unsubscribed: {run_id}")


def main() -> None:
    try:
        import importlib

        telegram_ext = importlib.import_module("telegram.ext")
        Application = getattr(telegram_ext, "Application")
        CommandHandler = getattr(telegram_ext, "CommandHandler")
        MessageHandler = getattr(telegram_ext, "MessageHandler")
        filters = getattr(telegram_ext, "filters")
    except Exception as exc:
        raise SystemExit(
            "python-telegram-bot is not installed. Install with: pip install -e '.[app]'"
        ) from exc

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is required")
    api_base = os.environ.get("PYBT_SERVER_URL", "http://127.0.0.1:8765")
    api_key = os.environ.get("PYBT_API_KEY", "")
    if not api_key:
        raise SystemExit("PYBT_API_KEY is required (same as server)")

    allowed = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "")
    allowed_user_ids = {int(x) for x in allowed.split(",") if x.strip()} if allowed else set()
    if not allowed_user_ids:
        raise SystemExit("TELEGRAM_ALLOWED_USER_IDS is required (comma-separated user ids)")

    state = BotState(
        api_base=api_base,
        api_key=api_key,
        allowed_user_ids=allowed_user_ids,
        pending_run=set(),
        subscriptions={},
    )

    app = Application.builder().token(token).build()
    app.bot_data["state"] = state

    app.add_handler(CommandHandler(["help", "start"], cmd_help))
    app.add_handler(CommandHandler("configs", cmd_configs))
    app.add_handler(CommandHandler("runs", cmd_runs))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("subscribe", cmd_subscribe))
    app.add_handler(CommandHandler("unsubscribe", cmd_unsubscribe))

    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
