from __future__ import annotations

import asyncio
import hmac
import inspect
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx
from pybt.live.notify import NotificationOutbox, OutboxNotifierWorker

# Telegram is an optional dependency. We import it at runtime in main() so that
# `import pybt` and `pytest` work without the app extras installed.

LOGGER = logging.getLogger(__name__)


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


def _fmt_dt(value: Any) -> str:
    # Server returns ISO8601 strings for datetimes. Keep it readable.
    if value is None:
        return "-"
    s = str(value)
    s = s.replace("T", " ")
    if s.endswith("+00:00"):
        s = s[: -len("+00:00")] + "Z"
    return s


def _fmt_short(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _format_run_status(status: Any) -> str:
    if not isinstance(status, dict):
        return _fmt_short(status)
    run_id = status.get("run_id")
    state = status.get("state")
    config_name = status.get("config_name")
    pid = status.get("pid")
    started_at = status.get("started_at")
    ended_at = status.get("ended_at")
    last_seq = status.get("last_seq")
    err = status.get("error")
    lines = [
        f"Run: {run_id}",
        f"State: {state}",
        f"Config: {config_name}",
        f"PID: {_fmt_short(pid)}",
        f"Started: {_fmt_dt(started_at)}",
        f"Ended: {_fmt_dt(ended_at)}",
        f"Last seq: {_fmt_short(last_seq)}",
    ]
    if err:
        lines.append(f"Error: {err}")
    return "\n".join(lines)


def _format_summary_response(resp: Any) -> str:
    if not isinstance(resp, dict):
        return _fmt_short(resp)
    if not resp.get("ok"):
        err = resp.get("error")
        if isinstance(err, dict) and isinstance(err.get("message"), str):
            return f"Summary not available: {err['message']}"
        return f"Summary not available: {_fmt_short(err)}"
    summary = resp.get("summary")
    if not isinstance(summary, dict):
        return _fmt_short(summary)

    # Highlight a few common metrics first.
    highlight_keys = [
        "equity",
        "cash",
        "max_drawdown",
        "total_trades",
        "sharpe",
        "return",
    ]
    lines: list[str] = []
    for k in highlight_keys:
        if k in summary:
            lines.append(f"{k}: {_fmt_short(summary.get(k))}")

    # Then include the remaining top-level keys (bounded).
    remaining = [k for k in summary.keys() if k not in highlight_keys]
    for k in sorted(remaining)[:12]:
        lines.append(f"{k}: {_fmt_short(summary.get(k))}")

    if not lines:
        return "(empty summary)"
    return "\n".join(lines)


_TELEGRAM_MODULE: Any = None


def _telegram() -> Any:
    """Import telegram lazily to keep pybt import/test lightweight."""

    global _TELEGRAM_MODULE
    if _TELEGRAM_MODULE is not None:
        return _TELEGRAM_MODULE
    import importlib

    _TELEGRAM_MODULE = importlib.import_module("telegram")
    return _TELEGRAM_MODULE


def _is_private_chat(update: Any) -> bool:
    chat = getattr(update, "effective_chat", None)
    return chat is not None and getattr(chat, "type", None) == "private"


@dataclass
class BotState:
    api_base: str
    api_key: str
    admin_password: str
    auth_file: Path
    authed_user_ids: set[int]
    pending_run: set[int]
    subscriptions: dict[tuple[int, str], asyncio.Task]


class ApiClientError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def _extract_server_error_message(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    err = payload.get("error")
    if isinstance(err, str) and err:
        return err
    if isinstance(err, dict):
        msg = err.get("message")
        if isinstance(msg, str) and msg:
            hint = err.get("hint")
            request_id = err.get("request_id")
            out = msg
            if isinstance(hint, str) and hint:
                out = f"{out} (hint: {hint})"
            if isinstance(request_id, str) and request_id:
                out = f"{out} [request_id={request_id}]"
            return out
    return None


async def _api(
    client: httpx.AsyncClient,
    state: BotState,
    method: str,
    path: str,
    json_body: Any = None,
) -> Any:
    url = state.api_base.rstrip("/") + path
    headers = {"X-API-Key": state.api_key}
    resp = await client.request(
        method, url, headers=headers, json=json_body, timeout=30
    )
    payload: Any = None
    try:
        payload = resp.json()
    except Exception:
        payload = None

    # server returns ok=false for HTTPException too; prefer status for flow.
    if resp.status_code >= 400:
        message = _extract_server_error_message(payload)
        if not message:
            text = (resp.text or "").strip()
            message = text[:240] if text else "request failed"
        raise ApiClientError(resp.status_code, message)

    if payload is None:
        raise ApiClientError(resp.status_code, "Invalid JSON response from server")
    return payload


def _check_auth(state: BotState, update: Any) -> bool:
    user = update.effective_user
    if user is None:
        return False
    return user.id in state.authed_user_ids


def _default_base_dir() -> Path:
    return Path(os.environ.get("PYBT_BASE_DIR", str(Path.home() / ".pybt")))


def _load_authed_user_ids(path: Path) -> set[int]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return set()
    except Exception:
        # Corrupted file: fail closed.
        return set()
    if not isinstance(raw, dict):
        return set()
    ids = raw.get("authed_user_ids", [])
    if not isinstance(ids, list):
        return set()
    out: set[int] = set()
    for x in ids:
        try:
            out.add(int(x))
        except Exception:
            continue
    return out


def _save_authed_user_ids(path: Path, ids: set[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps({"authed_user_ids": sorted(ids)}, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)


async def cmd_help(update: Any, context: Any) -> None:
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
            "/login <password>",
            "/logout",
            "/menu",
        ]
    )
    await update.message.reply_text(text, reply_markup=_menu_markup(update))  # type: ignore[union-attr]


async def cmd_menu(update: Any, context: Any) -> None:
    msg = update.message
    if msg is None:
        return
    await msg.reply_text("Menu:", reply_markup=_menu_markup(update))


async def cmd_login(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    msg = update.message
    if msg is None:
        return
    # Avoid leaking secrets in group chats.
    chat = update.effective_chat
    if chat is not None and getattr(chat, "type", None) != "private":
        await msg.reply_text("Please /login in a private chat with the bot.")
        return
    if not context.args:
        await msg.reply_text("Usage: /login <password>")
        return
    supplied = context.args[0]
    if not hmac.compare_digest(supplied, state.admin_password):
        await msg.reply_text("Invalid password")
        return
    user = update.effective_user
    if user is None:
        return
    state.authed_user_ids.add(int(user.id))
    _save_authed_user_ids(state.auth_file, state.authed_user_ids)
    await msg.reply_text("Login successful", reply_markup=_menu_markup(update))


async def cmd_logout(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    msg = update.message
    if msg is None:
        return
    user = update.effective_user
    if user is None:
        return
    state.authed_user_ids.discard(int(user.id))
    _save_authed_user_ids(state.auth_file, state.authed_user_ids)
    await msg.reply_text("Logged out", reply_markup=_menu_markup(update))


def _inline_menu_markup() -> Any:
    telegram = _telegram()
    InlineKeyboardButton = getattr(telegram, "InlineKeyboardButton")
    InlineKeyboardMarkup = getattr(telegram, "InlineKeyboardMarkup")
    keyboard = [
        [
            InlineKeyboardButton("Runs", callback_data="menu:runs"),
            InlineKeyboardButton("Configs", callback_data="menu:configs"),
        ],
        [
            InlineKeyboardButton("Run", callback_data="menu:run"),
            InlineKeyboardButton("Help", callback_data="menu:help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _reply_menu_markup() -> Any:
    telegram = _telegram()
    ReplyKeyboardMarkup = getattr(telegram, "ReplyKeyboardMarkup")
    keyboard = [
        ["Runs", "Configs"],
        ["Run", "Help"],
        ["Logout"],
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Select an action",
    )


def _pending_run_markup(update: Any) -> Any:
    # Only used in private chats; in groups we avoid reply keyboards.
    if not _is_private_chat(update):
        return None
    telegram = _telegram()
    ReplyKeyboardMarkup = getattr(telegram, "ReplyKeyboardMarkup")
    keyboard = [["Cancel"]]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Paste JSON or Cancel",
    )


def _menu_markup(update: Any) -> Any:
    # In private chats, a ReplyKeyboard is more convenient for repeated use.
    # In groups, prefer inline buttons to avoid hijacking everyone's input.
    return _reply_menu_markup() if _is_private_chat(update) else _inline_menu_markup()


def _require_auth_for_callback(state: BotState, update: Any) -> bool:
    """Return True if user is authed; show guidance via CBQ otherwise."""

    if _check_auth(state, update):
        return True
    return False


async def on_button(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    query = update.callback_query
    if query is None:
        return

    data = getattr(query, "data", "")
    # Always answer callback queries to clear the client spinner.
    await query.answer()

    if data == "menu:help":
        # Reuse help content.
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
                "/login <password>",
                "/logout",
            ]
        )
        await query.edit_message_text(text=text, reply_markup=_inline_menu_markup())
        return

    if data in {"menu:runs", "menu:configs"} and not _require_auth_for_callback(
        state, update
    ):
        await query.answer("Please /login in private chat first", show_alert=True)
        return

    if data == "menu:runs":
        await _button_show_runs(query, context, state)
        return
    if data == "menu:configs":
        await _button_show_configs(query, context, state)
        return
    if data == "menu:run":
        if not _require_auth_for_callback(state, update):
            await query.answer("Please /login in private chat first", show_alert=True)
            return
        await _button_run_start(query, context, state)
        return

    # Run actions.
    if isinstance(data, str) and data.startswith("run:"):
        if not _require_auth_for_callback(state, update):
            await query.answer("Please /login in private chat first", show_alert=True)
            return
        await _button_run_action(query, context, state, data)
        return

    if isinstance(data, str) and data.startswith("cfg:"):
        if not _require_auth_for_callback(state, update):
            await query.answer("Please /login in private chat first", show_alert=True)
            return
        await _button_config_action(query, context, state, data)
        return


async def _button_show_runs(query: Any, context: Any, state: BotState) -> None:
    async with httpx.AsyncClient() as client:
        data = await _api(client, state, "GET", "/runs")
    runs = data.get("runs", [])
    if not isinstance(runs, list) or not runs:
        await query.edit_message_text(
            text="No runs", reply_markup=_inline_menu_markup()
        )
        return

    # Cache runs in user_data to keep callback_data small.
    ctx_runs: list[dict[str, Any]] = [r for r in runs if isinstance(r, dict)]
    context.user_data["runs_cache"] = ctx_runs[:20]

    telegram = _telegram()
    InlineKeyboardButton = getattr(telegram, "InlineKeyboardButton")
    InlineKeyboardMarkup = getattr(telegram, "InlineKeyboardMarkup")

    keyboard = []
    for i, r in enumerate(context.user_data["runs_cache"]):
        rid = str(r.get("run_id", ""))
        st = str(r.get("state", ""))
        label = rid if len(rid) <= 12 else rid[:12] + "..."
        keyboard.append(
            [InlineKeyboardButton(f"{label} ({st})", callback_data=f"run:menu:{i}")]
        )
    keyboard.append([InlineKeyboardButton("Back", callback_data="menu:help")])

    await query.edit_message_text(
        text="Select a run:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _button_show_configs(query: Any, context: Any, state: BotState) -> None:
    async with httpx.AsyncClient() as client:
        data = await _api(client, state, "GET", "/configs")
    items = data.get("configs", [])
    if not isinstance(items, list) or not items:
        await query.edit_message_text(
            text="No configs", reply_markup=_inline_menu_markup()
        )
        return

    # Cache config metadata for per-user selection.
    cfgs: list[dict[str, Any]] = [it for it in items if isinstance(it, dict)][:20]
    context.user_data["configs_cache"] = cfgs

    telegram = _telegram()
    InlineKeyboardButton = getattr(telegram, "InlineKeyboardButton")
    InlineKeyboardMarkup = getattr(telegram, "InlineKeyboardMarkup")

    keyboard = []
    for i, cfg in enumerate(cfgs):
        name = str(cfg.get("name", ""))
        label = name if len(name) <= 20 else name[:20] + "..."
        keyboard.append([InlineKeyboardButton(label, callback_data=f"cfg:menu:{i}")])
    keyboard.append([InlineKeyboardButton("Back", callback_data="menu:help")])

    await query.edit_message_text(
        text="Select a config:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _button_config_action(
    query: Any, context: Any, state: BotState, data: str
) -> None:
    # Supported actions:
    # - cfg:menu:<idx>
    # - cfg:run:<idx>
    parts = data.split(":", 2)
    if len(parts) != 3:
        return
    _, action, idx_s = parts
    try:
        idx = int(idx_s)
    except Exception:
        return
    cfgs: list[dict[str, Any]] = context.user_data.get("configs_cache", [])
    if not isinstance(cfgs, list) or idx < 0 or idx >= len(cfgs):
        await query.edit_message_text(
            text="Config list expired. Tap Configs again.",
            reply_markup=_inline_menu_markup(),
        )
        return
    cfg = cfgs[idx]
    name = str(cfg.get("name", ""))
    size = cfg.get("size_bytes")

    telegram = _telegram()
    InlineKeyboardButton = getattr(telegram, "InlineKeyboardButton")
    InlineKeyboardMarkup = getattr(telegram, "InlineKeyboardMarkup")

    if action == "menu":
        keyboard = [
            [InlineKeyboardButton("Run", callback_data=f"cfg:run:{idx}")],
            [InlineKeyboardButton("Back", callback_data="menu:configs")],
        ]
        await query.edit_message_text(
            text=f"Config: {name}\nSize: {size}",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if action == "run":
        async with httpx.AsyncClient() as client:
            run = await _api(client, state, "POST", "/runs", {"config_name": name})
        run_id = run.get("run_id")
        await query.edit_message_text(
            text=f"Started run: {run_id}\nConfig: {name}",
            reply_markup=_inline_menu_markup(),
        )
        return


async def _button_run_start(query: Any, context: Any, state: BotState) -> None:
    telegram = _telegram()
    InlineKeyboardButton = getattr(telegram, "InlineKeyboardButton")
    InlineKeyboardMarkup = getattr(telegram, "InlineKeyboardMarkup")

    keyboard = [
        [
            InlineKeyboardButton("Paste JSON", callback_data="run:pending:on"),
            InlineKeyboardButton("Upload config.json", callback_data="run:upload:on"),
            InlineKeyboardButton("Cancel", callback_data="run:pending:off"),
        ],
        [InlineKeyboardButton("Back", callback_data="menu:help")],
    ]
    await query.edit_message_text(
        text="Run mode: send config.json (document) or paste JSON text.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _button_run_action(
    query: Any, context: Any, state: BotState, data: str
) -> None:
    # Supported actions:
    # - run:menu:<idx>
    # - run:status:<idx>
    # - run:summary:<idx>
    # - run:stop:<idx>
    # - run:sub:<idx>
    # - run:unsub:<idx>
    parts = data.split(":", 2)
    if len(parts) != 3:
        return
    _, action, idx_s = parts

    if action in {"pending", "upload"}:
        # idx_s is 'on'/'off'
        user = getattr(query, "from_user", None)
        if user is None:
            return
        user_id = int(getattr(user, "id", 0))

        telegram = _telegram()
        InlineKeyboardButton = getattr(telegram, "InlineKeyboardButton")
        InlineKeyboardMarkup = getattr(telegram, "InlineKeyboardMarkup")
        controls = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Cancel", callback_data="run:pending:off"),
                    InlineKeyboardButton("Menu", callback_data="menu:help"),
                ]
            ]
        )

        if idx_s == "on" and action == "pending":
            state.pending_run.add(user_id)
            await query.edit_message_text(
                text="OK. Paste JSON in your next message, or upload config.json as a document.\nSend 'Cancel' to abort.",
                reply_markup=controls,
            )
            return
        if idx_s == "on" and action == "upload":
            state.pending_run.add(user_id)
            await query.edit_message_text(
                text="OK. Now upload config.json (as a document) in this chat.\nTip: you can caption the file with /run, but it's not required while run mode is active.",
                reply_markup=controls,
            )
            return
        if idx_s == "off":
            state.pending_run.discard(user_id)
            await query.edit_message_text(
                text="Cancelled run mode.",
                reply_markup=_inline_menu_markup(),
            )
            return

    try:
        idx = int(idx_s)
    except Exception:
        return
    runs: list[dict[str, Any]] = context.user_data.get("runs_cache", [])
    if not isinstance(runs, list) or idx < 0 or idx >= len(runs):
        await query.edit_message_text(
            text="Run list expired. Tap Runs again.",
            reply_markup=_inline_menu_markup(),
        )
        return

    run_id = str(runs[idx].get("run_id", ""))
    if not run_id:
        return

    telegram = _telegram()
    InlineKeyboardButton = getattr(telegram, "InlineKeyboardButton")
    InlineKeyboardMarkup = getattr(telegram, "InlineKeyboardMarkup")

    if action == "menu":
        keyboard = [
            [
                InlineKeyboardButton("Status", callback_data=f"run:status:{idx}"),
                InlineKeyboardButton("Summary", callback_data=f"run:summary:{idx}"),
            ],
            [
                InlineKeyboardButton("Stop", callback_data=f"run:stop:{idx}"),
                InlineKeyboardButton("Subscribe", callback_data=f"run:sub:{idx}"),
                InlineKeyboardButton("Unsubscribe", callback_data=f"run:unsub:{idx}"),
            ],
            [InlineKeyboardButton("Back", callback_data="menu:runs")],
        ]
        await query.edit_message_text(
            text=f"Run: {run_id}",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if action in {"status", "summary"}:
        path = f"/runs/{run_id}" if action == "status" else f"/runs/{run_id}/summary"
        async with httpx.AsyncClient() as client:
            payload = await _api(client, state, "GET", path)
        await query.edit_message_text(
            text=_format_run_status(payload)
            if action == "status"
            else _format_summary_response(payload),
            reply_markup=_inline_menu_markup(),
        )
        return

    if action == "stop":
        async with httpx.AsyncClient() as client:
            await _api(client, state, "POST", f"/runs/{run_id}/stop")
        await query.edit_message_text(
            text=f"Stop requested: {run_id}",
            reply_markup=_inline_menu_markup(),
        )
        return

    # Subscribe/unsubscribe are per-chat.
    chat_id = getattr(getattr(query, "message", None), "chat_id", None)
    if not isinstance(chat_id, int):
        return
    if action == "sub":
        # Reuse the existing streaming implementation.
        key = (chat_id, run_id)
        if key in state.subscriptions:
            await query.answer("Already subscribed", show_alert=False)
            return

        # Create a minimal fake update-like object is not worth it; call the underlying logic.
        # We keep subscription code in cmd_subscribe; here we emulate the key insert.
        async def stream_loop() -> None:
            ws_url = state.api_base.rstrip("/")
            if ws_url.startswith("https://"):
                ws_url = "wss://" + ws_url[len("https://") :]
            elif ws_url.startswith("http://"):
                ws_url = "ws://" + ws_url[len("http://") :]
            ws_url = (
                f"{ws_url}/runs/{run_id}/stream"
                "?types=FillEvent,MetricsEvent,NotificationIntentEvent"
            )
            outbox = NotificationOutbox(_subscription_outbox_path(run_id, chat_id))

            async def send_from_outbox(msg: Any) -> None:
                payload = msg.payload
                await context.bot.send_message(
                    chat_id=int(payload["chat_id"]),
                    text=str(payload["text"]),
                )

            delivery_worker = OutboxNotifierWorker(
                outbox=outbox,
                sender=send_from_outbox,
                retry_delay_seconds=2,
                max_attempts=5,
            )

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
                                    if isinstance(ev, dict):
                                        _queue_event_for_delivery(
                                            outbox=outbox,
                                            run_id=run_id,
                                            chat_id=chat_id,
                                            ev=ev,
                                        )
                            await delivery_worker.process_once_async(
                                limit=200,
                                now=datetime.utcnow(),
                            )
                except asyncio.CancelledError:
                    return
                except Exception:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 10.0)

        task = asyncio.create_task(stream_loop())
        state.subscriptions[key] = task
        await query.edit_message_text(
            text=f"Subscribed: {run_id}",
            reply_markup=_inline_menu_markup(),
        )
        return

    if action == "unsub":
        key = (chat_id, run_id)
        task = state.subscriptions.pop(key, None)
        if task is None:
            await query.answer("Not subscribed", show_alert=False)
            return
        task.cancel()
        await query.edit_message_text(
            text=f"Unsubscribed: {run_id}",
            reply_markup=_inline_menu_markup(),
        )
        return


async def cmd_configs(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        await update.message.reply_text(
            "Please /login <password> in a private chat first"
        )  # type: ignore[union-attr]
        return
    async with httpx.AsyncClient() as client:
        data = await _api(client, state, "GET", "/configs")
    items = data.get("configs", [])
    if not items:
        await update.message.reply_text("No configs")  # type: ignore[union-attr]
        return

    cfgs: list[dict[str, Any]] = [it for it in items if isinstance(it, dict)][:20]
    context.user_data["configs_cache"] = cfgs

    telegram = _telegram()
    InlineKeyboardButton = getattr(telegram, "InlineKeyboardButton")
    InlineKeyboardMarkup = getattr(telegram, "InlineKeyboardMarkup")

    keyboard = []
    for i, cfg in enumerate(cfgs):
        name = str(cfg.get("name", ""))
        label = name if len(name) <= 20 else name[:20] + "..."
        keyboard.append([InlineKeyboardButton(label, callback_data=f"cfg:menu:{i}")])
    keyboard.append([InlineKeyboardButton("Menu", callback_data="menu:help")])

    await update.message.reply_text(
        "Select a config:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )  # type: ignore[union-attr]


async def cmd_runs(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        await update.message.reply_text(
            "Please /login <password> in a private chat first"
        )  # type: ignore[union-attr]
        return
    async with httpx.AsyncClient() as client:
        data = await _api(client, state, "GET", "/runs")
    runs = data.get("runs", [])
    if not runs:
        await update.message.reply_text("No runs")  # type: ignore[union-attr]
        return

    ctx_runs: list[dict[str, Any]] = [r for r in runs if isinstance(r, dict)][:20]
    context.user_data["runs_cache"] = ctx_runs

    telegram = _telegram()
    InlineKeyboardButton = getattr(telegram, "InlineKeyboardButton")
    InlineKeyboardMarkup = getattr(telegram, "InlineKeyboardMarkup")

    keyboard = []
    for i, r in enumerate(ctx_runs):
        rid = str(r.get("run_id", ""))
        st = str(r.get("state", ""))
        label = rid if len(rid) <= 12 else rid[:12] + "..."
        keyboard.append(
            [InlineKeyboardButton(f"{label} ({st})", callback_data=f"run:menu:{i}")]
        )
    keyboard.append([InlineKeyboardButton("Menu", callback_data="menu:help")])

    await update.message.reply_text(
        "Select a run:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )  # type: ignore[union-attr]


async def cmd_status(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        await update.message.reply_text(
            "Please /login <password> in a private chat first"
        )  # type: ignore[union-attr]
        return
    if not context.args:
        await update.message.reply_text("Usage: /status <run_id>")  # type: ignore[union-attr]
        return
    run_id = context.args[0]
    async with httpx.AsyncClient() as client:
        data = await _api(client, state, "GET", f"/runs/{run_id}")
    await update.message.reply_text(
        _format_run_status(data),
        reply_markup=_menu_markup(update),
    )  # type: ignore[union-attr]


async def cmd_summary(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        await update.message.reply_text(
            "Please /login <password> in a private chat first"
        )  # type: ignore[union-attr]
        return
    if not context.args:
        await update.message.reply_text("Usage: /summary <run_id>")  # type: ignore[union-attr]
        return
    run_id = context.args[0]
    async with httpx.AsyncClient() as client:
        data = await _api(client, state, "GET", f"/runs/{run_id}/summary")
    await update.message.reply_text(
        _format_summary_response(data),
        reply_markup=_menu_markup(update),
    )  # type: ignore[union-attr]


async def cmd_stop(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        await update.message.reply_text(
            "Please /login <password> in a private chat first"
        )  # type: ignore[union-attr]
        return
    if not context.args:
        await update.message.reply_text("Usage: /stop <run_id>")  # type: ignore[union-attr]
        return
    run_id = context.args[0]
    async with httpx.AsyncClient() as client:
        await _api(client, state, "POST", f"/runs/{run_id}/stop")
    await update.message.reply_text(
        f"Stop requested: {run_id}",
        reply_markup=_menu_markup(update),
    )  # type: ignore[union-attr]


async def cmd_run(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        await update.message.reply_text(
            "Please /login <password> in a private chat first"
        )  # type: ignore[union-attr]
        return
    msg = update.message
    if msg is None:
        return

    args = getattr(context, "args", None) or []

    # Inline JSON: /run { ... }
    if args:
        raw = msg.text
        if raw is None:
            return
        json_part = raw.split(" ", 1)[1] if " " in raw else ""
        if not json_part.strip():
            await msg.reply_text("Paste JSON after /run or send config.json")
            return
        await _run_from_json_text(update, context, json_part, from_pending=False)
        return

    # No args: enter pending mode (next message is JSON text or config.json upload).
    state.pending_run.add(update.effective_user.id)  # type: ignore[union-attr]
    await msg.reply_text(
        "Run mode enabled. Send config.json (document) or paste JSON text. Send 'Cancel' to abort.",
        reply_markup=_pending_run_markup(update),
    )


async def _run_from_json_text(
    update: Any, context: Any, text: str, *, from_pending: bool
) -> None:
    state: BotState = context.bot_data["state"]
    msg = update.message
    if msg is None:
        return
    user_id = update.effective_user.id  # type: ignore[union-attr]
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

    if from_pending:
        state.pending_run.discard(user_id)

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
        ),
        reply_markup=_menu_markup(update),
    )


async def on_document(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        await update.message.reply_text(
            "Please /login <password> in a private chat first"
        )  # type: ignore[union-attr]
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

    config_name = f"tg_{update.effective_chat.id}_{_utc_stamp()}.json"  # type: ignore[union-attr]

    async with httpx.AsyncClient() as client:
        valid = await _api(client, state, "POST", "/configs/validate", {"config": cfg})
        if not valid.get("ok"):
            err = valid.get("error", {}).get("message", "validation failed")
            await msg.reply_text(f"Config validate failed: {err}")
            return
        await _api(client, state, "POST", f"/configs/{config_name}", cfg)
        run = await _api(client, state, "POST", "/runs", {"config_name": config_name})

    # Clear pending state only after success.
    state.pending_run.discard(user_id)
    run_id = run.get("run_id")
    await msg.reply_text(
        f"Started run: {run_id}\n/subscribe {run_id}",
        reply_markup=_menu_markup(update),
    )


async def on_text(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    msg = update.message
    if msg is None or msg.text is None:
        return
    text = msg.text.strip()

    # Allow Help even before login (useful when users only see the reply keyboard).
    if text == "Help":
        await cmd_help(update, context)
        return

    if text == "Menu":
        await cmd_menu(update, context)
        return

    if (
        _is_private_chat(update)
        and (not _check_auth(state, update))
        and text in {"Runs", "Configs", "Run", "Logout"}
    ):
        await msg.reply_text(
            "Please /login <password> first",
            reply_markup=_menu_markup(update),
        )
        return

    if not _check_auth(state, update):
        return

    user_id = update.effective_user.id  # type: ignore[union-attr]

    if text.lower() == "cancel":
        if user_id in state.pending_run:
            state.pending_run.discard(user_id)
            await msg.reply_text("Cancelled.", reply_markup=_menu_markup(update))
        return

    # Private-chat menu shortcuts (ReplyKeyboardMarkup sends plain text messages).
    if _is_private_chat(update) and user_id not in state.pending_run:
        if text == "Runs":
            await cmd_runs(update, context)
            return
        if text == "Configs":
            await cmd_configs(update, context)
            return
        if text == "Run":
            await cmd_run(update, context)
            return
        if text == "Logout":
            await cmd_logout(update, context)
            return

    if user_id not in state.pending_run:
        return

    # Treat next text message as JSON config. Keep pending mode on failures.
    await _run_from_json_text(update, context, msg.text, from_pending=True)


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
    if et == "NotificationIntentEvent":
        if isinstance(data, dict):
            message = data.get("message")
            if isinstance(message, str) and message:
                return message
    return None


def _subscription_outbox_path(run_id: str, chat_id: int) -> Path:
    return _default_base_dir() / "telegram_outbox" / f"{chat_id}_{run_id}.sqlite3"


def _event_dedupe_key(run_id: str, ev: dict[str, Any]) -> str:
    data = ev.get("data", {})
    if isinstance(data, dict):
        key = data.get("dedupe_key")
        if isinstance(key, str) and key:
            return key
    seq = ev.get("seq")
    event_type = ev.get("event_type", "Event")
    return f"{run_id}:{seq}:{event_type}"


def _queue_event_for_delivery(
    *, outbox: NotificationOutbox, run_id: str, chat_id: int, ev: dict[str, Any]
) -> bool:
    text = _format_event(ev)
    if not text:
        return False
    event_type = str(ev.get("event_type", "Event"))
    payload = {
        "chat_id": chat_id,
        "text": text,
        "run_id": run_id,
        "event_type": event_type,
        "seq": ev.get("seq"),
    }
    outbox.enqueue(
        event_type=event_type,
        payload=payload,
        dedupe_key=_event_dedupe_key(run_id=run_id, ev=ev),
    )
    return True


async def cmd_subscribe(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        await update.message.reply_text(
            "Please /login <password> in a private chat first"
        )  # type: ignore[union-attr]
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
        ws_url = (
            f"{ws_url}/runs/{run_id}/stream"
            "?types=FillEvent,MetricsEvent,NotificationIntentEvent"
        )
        outbox = NotificationOutbox(_subscription_outbox_path(run_id, chat_id))

        async def send_from_outbox(msg: Any) -> None:
            payload = msg.payload
            await context.bot.send_message(
                chat_id=int(payload["chat_id"]),
                text=str(payload["text"]),
            )

        delivery_worker = OutboxNotifierWorker(
            outbox=outbox,
            sender=send_from_outbox,
            retry_delay_seconds=2,
            max_attempts=5,
        )

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
                                if isinstance(ev, dict):
                                    _queue_event_for_delivery(
                                        outbox=outbox,
                                        run_id=run_id,
                                        chat_id=chat_id,
                                        ev=ev,
                                    )
                        await delivery_worker.process_once_async(
                            limit=200,
                            now=datetime.utcnow(),
                        )
                        # heartbeat: ignore
            except asyncio.CancelledError:
                return
            except Exception:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 10.0)

    task = asyncio.create_task(stream_loop())
    state.subscriptions[key] = task
    await msg.reply_text(
        f"Subscribed: {run_id}",
        reply_markup=_menu_markup(update),
    )


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


async def _poll_events_loop(
    context: Any, state: BotState, chat_id: int, run_id: str
) -> None:
    since = 0
    outbox = NotificationOutbox(_subscription_outbox_path(run_id, chat_id))

    async def send_from_outbox(msg: Any) -> None:
        payload = msg.payload
        await context.bot.send_message(
            chat_id=int(payload["chat_id"]),
            text=str(payload["text"]),
        )

    delivery_worker = OutboxNotifierWorker(
        outbox=outbox,
        sender=send_from_outbox,
        retry_delay_seconds=2,
        max_attempts=5,
    )
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
                if isinstance(ev, dict):
                    _queue_event_for_delivery(
                        outbox=outbox,
                        run_id=run_id,
                        chat_id=chat_id,
                        ev=ev,
                    )
                since = max(since, int(ev.get("seq", since)))
            since = max(since, int(data.get("last_seq", since)))
            await delivery_worker.process_once_async(
                limit=200,
                now=datetime.utcnow(),
            )
            await asyncio.sleep(1.0)


async def cmd_unsubscribe(update: Any, context: Any) -> None:
    state: BotState = context.bot_data["state"]
    if not _check_auth(state, update):
        await update.message.reply_text(
            "Please /login <password> in a private chat first"
        )  # type: ignore[union-attr]
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
    await msg.reply_text(
        f"Unsubscribed: {run_id}",
        reply_markup=_menu_markup(update),
    )


async def _on_handler_error(update: Any, context: Any) -> None:
    err = getattr(context, "error", None)
    LOGGER.exception("telegram handler error", exc_info=err)

    msg = getattr(update, "effective_message", None)
    if msg is None:
        return
    if isinstance(err, ApiClientError):
        await msg.reply_text(f"Server request failed ({err.status_code}): {err}")
        return
    await msg.reply_text("Unexpected error. Please retry in a moment.")


def main() -> None:
    try:
        import importlib

        telegram_ext = importlib.import_module("telegram.ext")
        Application = getattr(telegram_ext, "Application")
        CommandHandler = getattr(telegram_ext, "CommandHandler")
        CallbackQueryHandler = getattr(telegram_ext, "CallbackQueryHandler")
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
    api_key = os.environ.get("PYBT_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("PYBT_API_KEY is required (same as server)")

    admin_password = os.environ.get("TELEGRAM_ADMIN_PASSWORD", "")
    if not admin_password:
        raise SystemExit("TELEGRAM_ADMIN_PASSWORD is required")

    auth_file = _default_base_dir() / "telegram_auth.json"
    authed_user_ids = _load_authed_user_ids(auth_file)

    state = BotState(
        api_base=api_base,
        api_key=api_key,
        admin_password=admin_password,
        auth_file=auth_file,
        authed_user_ids=authed_user_ids,
        pending_run=set(),
        subscriptions={},
    )

    app = Application.builder().token(token).build()
    app.bot_data["state"] = state

    app.add_handler(CommandHandler(["help", "start"], cmd_help))
    app.add_handler(CommandHandler("login", cmd_login))
    app.add_handler(CommandHandler("logout", cmd_logout))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("configs", cmd_configs))
    app.add_handler(CommandHandler("runs", cmd_runs))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("subscribe", cmd_subscribe))
    app.add_handler(CommandHandler("unsubscribe", cmd_unsubscribe))

    app.add_handler(CallbackQueryHandler(on_button))

    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(_on_handler_error)

    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
