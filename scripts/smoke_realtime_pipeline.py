#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.telegram_bot.telegram_bot import _queue_event_for_delivery
from pybt.configuration import load_engine_from_dict
from pybt.live import NotificationOutbox, OutboxNotifierWorker, build_smoke_config


def _request_json(
    *,
    base_url: str,
    api_key: str,
    method: str,
    path: str,
    body: Optional[dict[str, Any]] = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    headers = {"Accept": "application/json", "X-API-Key": api_key}
    data: Optional[bytes] = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = Request(url=url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"{method} {path} failed: HTTP {exc.code}: {detail}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"{method} {path} failed: {exc}") from exc

    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _wait_health(base_url: str, api_key: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Optional[str] = None
    while time.monotonic() < deadline:
        try:
            data = _request_json(
                base_url=base_url,
                api_key=api_key,
                method="GET",
                path="/health",
                timeout=2.0,
            )
            if str(data.get("ok", "")).lower() == "true":
                return
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.2)
    raise RuntimeError(
        f"Server health check timed out: {last_error or 'unknown error'}"
    )


def _start_server(
    base_dir: Path, host: str, port: int, api_key: str
) -> subprocess.Popen[Any]:
    env = os.environ.copy()
    env["PYBT_SERVER_HOST"] = host
    env["PYBT_SERVER_PORT"] = str(port)
    env["PYBT_API_KEY"] = api_key
    env["PYBT_BASE_DIR"] = str(base_dir)
    env.setdefault("PYBT_MAX_CONCURRENT_RUNS", "2")
    return subprocess.Popen(
        [sys.executable, "-m", "apps.server"],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _stop_process(proc: subprocess.Popen[Any]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _drain_events_once(
    *,
    base_url: str,
    api_key: str,
    run_id: str,
    since_seq: int,
    outbox: NotificationOutbox,
    chat_id: int,
) -> int:
    payload = _request_json(
        base_url=base_url,
        api_key=api_key,
        method="GET",
        path=f"/runs/{run_id}/events?since_seq={since_seq}&limit=200",
    )
    next_seq = since_seq
    events = payload.get("events", [])
    if isinstance(events, list):
        for ev in events:
            if isinstance(ev, dict):
                _queue_event_for_delivery(
                    outbox=outbox,
                    run_id=run_id,
                    chat_id=chat_id,
                    ev=ev,
                )
                try:
                    seq = int(ev.get("seq", next_seq))
                except Exception:
                    seq = next_seq
                if seq > next_seq:
                    next_seq = seq
    last_seq = payload.get("last_seq")
    if isinstance(last_seq, int) and last_seq > next_seq:
        next_seq = last_seq
    return next_seq


def run_smoke(
    *, base_dir: Path, host: str, port: int, api_key: str, timeout_seconds: float
) -> dict[str, Any]:
    base_url = f"http://{host}:{port}"
    proc = _start_server(base_dir=base_dir, host=host, port=port, api_key=api_key)
    try:
        _wait_health(base_url, api_key, timeout_seconds=15.0)
        config = build_smoke_config(symbol="AAA")

        try:
            load_engine_from_dict(config)
        except Exception as exc:
            raise RuntimeError(f"Local config validation failed: {exc}") from exc

        config_name = f"smoke_{int(time.time())}.json"
        _request_json(
            base_url=base_url,
            api_key=api_key,
            method="POST",
            path=f"/configs/{quote(config_name)}",
            body=config,
        )
        run_resp = _request_json(
            base_url=base_url,
            api_key=api_key,
            method="POST",
            path="/runs",
            body={"config_name": config_name},
        )
        run_id = str(run_resp.get("run_id", ""))
        if not run_id:
            raise RuntimeError(f"Run creation failed: {run_resp}")

        outbox = NotificationOutbox(
            base_dir / "telegram_outbox" / f"smoke_{run_id}.sqlite3"
        )
        delivered: list[str] = []

        def sender(msg: Any) -> None:
            text = str(msg.payload.get("text", ""))
            if text:
                delivered.append(text)

        worker = OutboxNotifierWorker(
            outbox=outbox,
            sender=sender,
            retry_delay_seconds=2,
            max_attempts=5,
        )

        since_seq = 0
        state = "starting"
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            since_seq = _drain_events_once(
                base_url=base_url,
                api_key=api_key,
                run_id=run_id,
                since_seq=since_seq,
                outbox=outbox,
                chat_id=1,
            )
            worker.process_once(limit=200, now=datetime.utcnow())

            status = _request_json(
                base_url=base_url,
                api_key=api_key,
                method="GET",
                path=f"/runs/{run_id}",
            )
            state = str(status.get("state", ""))
            if state in {"completed", "failed", "stopped"}:
                since_seq = _drain_events_once(
                    base_url=base_url,
                    api_key=api_key,
                    run_id=run_id,
                    since_seq=since_seq,
                    outbox=outbox,
                    chat_id=1,
                )
                worker.process_once(limit=200, now=datetime.utcnow())
                break
            time.sleep(0.2)

        if state != "completed":
            raise RuntimeError(f"Run did not complete successfully (state={state})")
        if not any(msg.startswith("SIGNAL ") for msg in delivered):
            raise RuntimeError("No strategy signal message reached outbox delivery")

        return {
            "run_id": run_id,
            "state": state,
            "messages": delivered,
            "config_name": config_name,
            "base_url": base_url,
        }
    finally:
        _stop_process(proc)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18765)
    parser.add_argument("--api-key", default="smoke-key")
    parser.add_argument("--base-dir", default="")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    if args.base_dir:
        base_dir = Path(args.base_dir)
        base_dir.mkdir(parents=True, exist_ok=True)
        result = run_smoke(
            base_dir=base_dir,
            host=args.host,
            port=args.port,
            api_key=args.api_key,
            timeout_seconds=args.timeout,
        )
    else:
        with tempfile.TemporaryDirectory(prefix="pybt_smoke_") as tmp:
            result = run_smoke(
                base_dir=Path(tmp),
                host=args.host,
                port=args.port,
                api_key=args.api_key,
                timeout_seconds=args.timeout,
            )

    messages = result["messages"]
    print(
        f"SMOKE PASS run_id={result['run_id']} state={result['state']} delivered={len(messages)}"
    )
    for idx, msg in enumerate(messages[:5], start=1):
        print(f"[{idx}] {msg}")


if __name__ == "__main__":
    main()
