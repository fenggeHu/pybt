from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, cast

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse

from pybt.configuration import load_engine_from_dict

from .config_store import ConfigNameError, ConfigStore
from .models import (
    ConfigSaveResponse,
    ConfigValidateRequest,
    ConfigValidateResponse,
    EventDTO,
    ErrorDTO,
    EventsResponse,
    RunCreateRequest,
    RunCreateResponse,
    RunState,
    RunStatusDTO,
    SummaryResponse,
)
from .run_manager import RunManager
from .settings import ServerSettings


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_app(settings: ServerSettings) -> FastAPI:
    app = FastAPI(title="pybt-server", version="0.1.0")

    store = ConfigStore(settings.configs_dir)
    runs = RunManager(
        runs_dir=settings.runs_dir, max_concurrent_runs=settings.max_concurrent_runs
    )

    def require_api_key(
        x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    ) -> None:
        if x_api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="invalid api key")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"ok": "true"}

    @app.get("/configs", dependencies=[Depends(require_api_key)])
    def list_configs() -> dict[str, Any]:
        return {"ok": True, "configs": store.list()}

    @app.post(
        "/configs/validate",
        response_model=ConfigValidateResponse,
        dependencies=[Depends(require_api_key)],
    )
    def validate_config(req: ConfigValidateRequest) -> ConfigValidateResponse:
        try:
            load_engine_from_dict(req.config)
            return ConfigValidateResponse(ok=True)
        except Exception as exc:
            return ConfigValidateResponse(ok=False, error=ErrorDTO(message=str(exc)))

    @app.get("/configs/{name}", dependencies=[Depends(require_api_key)])
    def get_config(name: str) -> dict[str, Any]:
        try:
            cfg = store.load(name)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="config not found")
        return {"ok": True, "name": name, "config": cfg}

    @app.post(
        "/configs/{name}",
        response_model=ConfigSaveResponse,
        dependencies=[Depends(require_api_key)],
    )
    def save_config(
        name: str, req: Mapping[str, Any], force: bool = False
    ) -> ConfigSaveResponse:
        if not isinstance(req, dict):
            raise HTTPException(
                status_code=400, detail="config body must be a JSON object"
            )
        try:
            store.save(name, req, force=force)
        except ConfigNameError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except FileExistsError:
            raise HTTPException(
                status_code=409, detail="config exists (use ?force=true to overwrite)"
            )
        return ConfigSaveResponse(name=name)

    @app.post(
        "/runs",
        response_model=RunCreateResponse,
        dependencies=[Depends(require_api_key)],
    )
    def create_run(req: RunCreateRequest) -> RunCreateResponse:
        if (req.config_name is None) == (req.config is None):
            raise HTTPException(
                status_code=400, detail="Provide exactly one of config_name or config"
            )

        if req.config_name is not None:
            try:
                cfg = store.load(req.config_name)
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail="config not found")
            config_name = req.config_name
        else:
            assert req.config is not None
            cfg = req.config
            # When the client provides raw config, it should have been saved already.
            config_name = "(inline)"

        try:
            rec = runs.start(config_name=config_name, config=cfg)
        except RuntimeError as exc:
            raise HTTPException(status_code=429, detail=str(exc))
        return RunCreateResponse(run_id=rec.run_id, config_name=rec.config_name)

    @app.get("/runs", dependencies=[Depends(require_api_key)])
    def list_runs() -> dict[str, Any]:
        items = []
        for r in runs.list():
            items.append(
                RunStatusDTO(
                    run_id=r.run_id,
                    state=cast(RunState, r.state),
                    pid=r.pid,
                    config_name=r.config_name,
                    started_at=r.started_at,
                    ended_at=r.ended_at,
                    error=r.error,
                    last_seq=r.last_seq,
                ).model_dump()
            )
        return {"ok": True, "runs": items}

    @app.get(
        "/runs/{run_id}",
        response_model=RunStatusDTO,
        dependencies=[Depends(require_api_key)],
    )
    def get_run(run_id: str) -> RunStatusDTO:
        try:
            r = runs.get(run_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="run not found")
        return RunStatusDTO(
            run_id=r.run_id,
            state=cast(RunState, r.state),
            pid=r.pid,
            config_name=r.config_name,
            started_at=r.started_at,
            ended_at=r.ended_at,
            error=r.error,
            last_seq=r.last_seq,
        )

    @app.post("/runs/{run_id}/stop", dependencies=[Depends(require_api_key)])
    def stop_run(run_id: str) -> dict[str, Any]:
        try:
            runs.stop_hard(run_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="run not found")
        return {"ok": True}

    @app.get(
        "/runs/{run_id}/events",
        response_model=EventsResponse,
        dependencies=[Depends(require_api_key)],
    )
    def get_events(
        run_id: str,
        limit: int = 200,
        since_seq: int = 0,
        type: Optional[str] = None,  # noqa: A002
    ) -> EventsResponse:
        limit = max(1, min(limit, 2000))
        try:
            last_seq, selected = runs.get_events(
                run_id, since_seq=since_seq, limit=limit, event_type=type
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="run not found")
        return EventsResponse(
            run_id=run_id,
            last_seq=last_seq,
            events=[
                EventDTO(
                    seq=e.seq,
                    received_at=e.received_at,
                    event_type=e.event_type,
                    timestamp=e.timestamp,
                    data=dict(e.data),
                )
                for e in selected
            ],
        )

    @app.websocket("/runs/{run_id}/stream")
    async def stream_events(
        websocket: WebSocket, run_id: str, types: Optional[str] = None
    ) -> None:
        # Auth via header for local-first safety.
        api_key = websocket.headers.get("x-api-key")
        if api_key != settings.api_key:
            await websocket.close(code=4401)
            return
        await websocket.accept()

        allowed_types: Optional[set[str]] = None
        if types:
            allowed_types = {t.strip() for t in types.split(",") if t.strip()}

        since_seq = 0
        try:
            while True:
                # Send new events in small batches.
                try:
                    last_seq, events = runs.get_events(
                        run_id, since_seq=since_seq, limit=500, event_type=None
                    )
                except KeyError:
                    await websocket.send_json(
                        {"kind": "error", "error": "run not found"}
                    )
                    await websocket.close(code=4404)
                    return

                out = []
                max_seen = since_seq
                for ev in events:
                    max_seen = max(max_seen, ev.seq)
                    if allowed_types is not None and ev.event_type not in allowed_types:
                        continue
                    out.append(
                        {
                            "seq": ev.seq,
                            "received_at": ev.received_at.isoformat(),
                            "event_type": ev.event_type,
                            "timestamp": ev.timestamp,
                            "data": dict(ev.data),
                        }
                    )
                # Always advance even if we filtered everything out, otherwise we'd
                # re-read and re-filter the same events forever.
                since_seq = max_seen

                if out:
                    await websocket.send_json(
                        {"kind": "events", "events": out, "last_seq": last_seq}
                    )
                else:
                    # Keep the connection alive and allow client to detect liveness.
                    await websocket.send_json(
                        {"kind": "heartbeat", "last_seq": last_seq}
                    )

                await asyncio.sleep(0.5)
        except WebSocketDisconnect:
            return

    @app.get(
        "/runs/{run_id}/summary",
        response_model=SummaryResponse,
        dependencies=[Depends(require_api_key)],
    )
    def get_summary(run_id: str) -> SummaryResponse:
        try:
            r = runs.get(run_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="run not found")
        if r.summary is None:
            if r.state in {"running", "starting"}:
                return SummaryResponse(
                    ok=False, run_id=run_id, error=ErrorDTO(message="run still running")
                )
            return SummaryResponse(
                ok=False, run_id=run_id, error=ErrorDTO(message="summary not available")
            )
        return SummaryResponse(ok=True, run_id=run_id, summary=r.summary)

    @app.exception_handler(HTTPException)
    def http_exception_handler(_, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content={"ok": False, "error": exc.detail}
        )

    return app
