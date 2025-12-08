import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from ..models import Run, RunCreate, RunStatus
from ..models import User
from ..services import enqueue_run, store
from ..services.auth import decode_token, get_current_user

router = APIRouter(tags=["runs"])


@router.get("/runs", response_model=list[Run])
async def list_runs(user: User = Depends(get_current_user)) -> list[Run]:
    return list(store.runs.values())


@router.get("/runs/{run_id}", response_model=Run)
async def get_run(run_id: str, user: User = Depends(get_current_user)) -> Run:
    run = store.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.post("/runs", response_model=Run)
async def create_run(payload: RunCreate, tasks: BackgroundTasks, user: User = Depends(get_current_user)) -> Run:
    config = payload.config
    if payload.config_id:
        cfg = store.configs.get(payload.config_id)
        if not cfg:
            raise HTTPException(status_code=404, detail="config not found")
        config = cfg.config
    if not config:
        raise HTTPException(status_code=400, detail="config or config_id is required")

    run = store.create_run(name=payload.name, config=config, config_id=payload.config_id)
    store.add_audit(actor=user.username, action="create_run", target=run.id)
    enqueue_run(run.id, tasks)
    return run


@router.post("/runs/{run_id}/cancel", response_model=Run)
async def cancel_run(run_id: str, user: User = Depends(get_current_user)) -> Run:
    run = store.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    if run.status in {RunStatus.succeeded, RunStatus.failed, RunStatus.cancelled}:
        return run
    run = store.update_run(run_id, {"status": RunStatus.cancelled, "message": "cancelled"})
    store.add_audit(actor=user.username, action="cancel_run", target=run_id)
    return run


async def _sse_stream(run_id: str) -> AsyncIterator[bytes]:
    queue = store.get_run_queue(run_id)
    if not queue:
        yield b"data: {\"error\": \"run not found\"}\n\n"
        return
    yield b"data: {\"type\": \"connected\"}\n\n"
    while True:
        event = await queue.get()
        payload = json.dumps(event, ensure_ascii=False)
        yield f"data: {payload}\n\n".encode("utf-8")


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str, request: Request) -> StreamingResponse:
    # Allow token via Authorization header or query param token= for EventSource
    header = request.headers.get("authorization")
    if header and header.lower().startswith("bearer "):
        decode_token(header.split(" ", 1)[1])
    else:
        token = request.query_params.get("token")
        if not token:
            raise HTTPException(status_code=401, detail="auth required")
        decode_token(token)
    return StreamingResponse(_sse_stream(run_id), media_type="text/event-stream")


@router.websocket("/runs/{run_id}/ws")
async def ws_run(websocket: WebSocket, run_id: str) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return
    try:
        from ..services.auth import decode_token

        decode_token(token)
    except Exception:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    queue = store.get_run_queue(run_id)
    if not queue:
        await websocket.send_json({"error": "run not found"})
        await websocket.close()
        return
    await websocket.send_json({"type": "connected"})
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return
