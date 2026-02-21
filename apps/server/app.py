from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from typing import Any, Mapping, Optional, cast

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse

from pybt.configuration import iter_definition_dicts, load_engine_from_dict

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


class ErrorCode(str, Enum):
    AUTH_INVALID_API_KEY = "auth_invalid_api_key"
    CONFIG_NOT_FOUND = "config_not_found"
    INVALID_CONFIG_BODY = "invalid_config_body"
    INVALID_CONFIG_NAME = "invalid_config_name"
    CONFIG_EXISTS = "config_exists"
    INVALID_RUN_REQUEST = "invalid_run_request"
    RUN_CAPACITY_EXCEEDED = "run_capacity_exceeded"
    RUN_NOT_FOUND = "run_not_found"
    RUN_STILL_RUNNING = "run_still_running"
    SUMMARY_NOT_AVAILABLE = "summary_not_available"
    INTERNAL_ERROR = "internal_error"
    HTTP_ERROR = "http_error"
    CONFIG_VALIDATION_ERROR = "config_validation_error"


class ErrorHint(str, Enum):
    PROVIDE_API_KEY = "Provide X-API-Key header"
    CHECK_CONFIGS = "Use /configs to inspect available config names."
    OVERWRITE_CONFIG = "Use ?force=true to overwrite an existing config."
    JSON_OBJECT_BODY = "Send a JSON object body for config payload."
    RUN_REQUEST_SHAPE = "Send either config_name or config, but not both."
    CHECK_RUNS = "Check /runs for available run IDs."
    RUN_CAPACITY = "Stop existing runs or increase PYBT_MAX_CONCURRENT_RUNS."
    RUN_STILL_RUNNING = "Retry after run state becomes completed/failed/stopped."
    SUMMARY_NOT_AVAILABLE = "Ensure reporters produce summary output for this run."


def _enum_text(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if isinstance(rid, str) and rid:
        return rid
    return "unknown"


def _error_payload(
    *,
    code: str,
    message: str,
    request_id: str,
    hint: Optional[str] = None,
    details: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": _enum_text(code),
        "message": message,
        "request_id": request_id,
    }
    if hint:
        payload["hint"] = hint
    if details:
        payload["details"] = dict(details)
    return payload


def _http_error(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    hint: Optional[str] = None,
    details: Optional[Mapping[str, Any]] = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=_error_payload(
            code=code,
            message=message,
            request_id=_request_id(request),
            hint=hint,
            details=details,
        ),
    )


def _coerce_http_error_detail(detail: Any, request_id: str) -> dict[str, Any]:
    if isinstance(detail, Mapping):
        code = _enum_text(detail.get("code", ErrorCode.HTTP_ERROR))
        message = str(detail.get("message", "request failed"))
        hint = detail.get("hint")
        details = detail.get("details")
        payload: dict[str, Any] = {
            "code": code,
            "message": message,
            "request_id": str(detail.get("request_id", request_id)),
        }
        if isinstance(hint, Enum):
            payload["hint"] = _enum_text(hint)
        elif isinstance(hint, str) and hint:
            payload["hint"] = hint
        if isinstance(details, Mapping):
            payload["details"] = dict(details)
        return payload
    if isinstance(detail, str) and detail:
        return {
            "code": ErrorCode.HTTP_ERROR,
            "message": detail,
            "request_id": request_id,
        }
    return {
        "code": ErrorCode.HTTP_ERROR,
        "message": "request failed",
        "request_id": request_id,
    }


def create_app(settings: ServerSettings) -> FastAPI:
    app = FastAPI(title="pybt-server", version="0.1.0")

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next: Any) -> Any:
        req_id = request.headers.get("x-request-id") or uuid4().hex
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response

    store = ConfigStore(settings.configs_dir)
    runs = RunManager(
        runs_dir=settings.runs_dir, max_concurrent_runs=settings.max_concurrent_runs
    )

    def require_api_key(
        request: Request,
        x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    ) -> None:
        if x_api_key != settings.api_key:
            raise _http_error(
                request,
                status_code=401,
                code=ErrorCode.AUTH_INVALID_API_KEY,
                message="invalid api key",
                hint=ErrorHint.PROVIDE_API_KEY,
            )

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/definitions", dependencies=[Depends(require_api_key)])
    def list_definitions() -> dict[str, Any]:
        return {"ok": True, "definitions": list(iter_definition_dicts())}

    @app.get("/configs", dependencies=[Depends(require_api_key)])
    def list_configs() -> dict[str, Any]:
        return {"ok": True, "configs": store.list()}

    @app.post(
        "/configs/validate",
        response_model=ConfigValidateResponse,
        dependencies=[Depends(require_api_key)],
    )
    def validate_config(
        req: ConfigValidateRequest, request: Request
    ) -> ConfigValidateResponse:
        try:
            load_engine_from_dict(req.config)
            return ConfigValidateResponse(ok=True)
        except Exception as exc:
            return ConfigValidateResponse(
                ok=False,
                error=ErrorDTO(
                    code=ErrorCode.CONFIG_VALIDATION_ERROR,
                    message=str(exc),
                    request_id=_request_id(request),
                ),
            )

    @app.get("/configs/{name}", dependencies=[Depends(require_api_key)])
    def get_config(name: str, request: Request) -> dict[str, Any]:
        try:
            cfg = store.load(name)
        except FileNotFoundError:
            raise _http_error(
                request,
                status_code=404,
                code=ErrorCode.CONFIG_NOT_FOUND,
                message="config not found",
                hint=ErrorHint.CHECK_CONFIGS,
                details={"name": name},
            )
        return {"ok": True, "name": name, "config": cfg}

    @app.post(
        "/configs/{name}",
        response_model=ConfigSaveResponse,
        dependencies=[Depends(require_api_key)],
    )
    def save_config(
        name: str, req: Mapping[str, Any], request: Request, force: bool = False
    ) -> ConfigSaveResponse:
        if not isinstance(req, dict):
            raise _http_error(
                request,
                status_code=400,
                code=ErrorCode.INVALID_CONFIG_BODY,
                message="config body must be a JSON object",
                hint=ErrorHint.JSON_OBJECT_BODY,
            )
        try:
            store.save(name, req, force=force)
        except ConfigNameError as exc:
            raise _http_error(
                request,
                status_code=400,
                code=ErrorCode.INVALID_CONFIG_NAME,
                message=str(exc),
            )
        except FileExistsError:
            raise _http_error(
                request,
                status_code=409,
                code=ErrorCode.CONFIG_EXISTS,
                message="config exists (use ?force=true to overwrite)",
                hint=ErrorHint.OVERWRITE_CONFIG,
                details={"name": name},
            )
        return ConfigSaveResponse(name=name)

    @app.post(
        "/runs",
        response_model=RunCreateResponse,
        dependencies=[Depends(require_api_key)],
    )
    def create_run(req: RunCreateRequest, request: Request) -> RunCreateResponse:
        if (req.config_name is None) == (req.config is None):
            raise _http_error(
                request,
                status_code=400,
                code=ErrorCode.INVALID_RUN_REQUEST,
                message="Provide exactly one of config_name or config",
                hint=ErrorHint.RUN_REQUEST_SHAPE,
            )

        if req.config_name is not None:
            try:
                cfg = store.load(req.config_name)
            except FileNotFoundError:
                raise _http_error(
                    request,
                    status_code=404,
                    code=ErrorCode.CONFIG_NOT_FOUND,
                    message="config not found",
                    hint=ErrorHint.CHECK_CONFIGS,
                    details={"name": req.config_name},
                )
            config_name = req.config_name
        else:
            assert req.config is not None
            cfg = req.config
            # When the client provides raw config, it should have been saved already.
            config_name = "(inline)"

        try:
            rec = runs.start(config_name=config_name, config=cfg)
        except RuntimeError as exc:
            raise _http_error(
                request,
                status_code=429,
                code=ErrorCode.RUN_CAPACITY_EXCEEDED,
                message=str(exc),
                hint=ErrorHint.RUN_CAPACITY,
            )
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
    def get_run(run_id: str, request: Request) -> RunStatusDTO:
        try:
            r = runs.get(run_id)
        except KeyError:
            raise _http_error(
                request,
                status_code=404,
                code=ErrorCode.RUN_NOT_FOUND,
                message="run not found",
                hint=ErrorHint.CHECK_RUNS,
                details={"run_id": run_id},
            )
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
    def stop_run(run_id: str, request: Request) -> dict[str, Any]:
        try:
            runs.stop_hard(run_id)
        except KeyError:
            raise _http_error(
                request,
                status_code=404,
                code=ErrorCode.RUN_NOT_FOUND,
                message="run not found",
                hint=ErrorHint.CHECK_RUNS,
                details={"run_id": run_id},
            )
        return {"ok": True}

    @app.get(
        "/runs/{run_id}/events",
        response_model=EventsResponse,
        dependencies=[Depends(require_api_key)],
    )
    def get_events(
        request: Request,
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
            raise _http_error(
                request,
                status_code=404,
                code=ErrorCode.RUN_NOT_FOUND,
                message="run not found",
                hint=ErrorHint.CHECK_RUNS,
                details={"run_id": run_id},
            )
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
        request_id = websocket.headers.get("x-request-id") or uuid4().hex
        api_key = websocket.headers.get("x-api-key")
        if api_key != settings.api_key:
            await websocket.accept()
            await websocket.send_json(
                {
                    "kind": "error",
                    "error": _error_payload(
                        code=ErrorCode.AUTH_INVALID_API_KEY,
                        message="invalid api key",
                        request_id=request_id,
                        hint=ErrorHint.PROVIDE_API_KEY,
                    ),
                }
            )
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
                        {
                            "kind": "error",
                            "error": _error_payload(
                                code=ErrorCode.RUN_NOT_FOUND,
                                message="run not found",
                                request_id=request_id,
                                hint=ErrorHint.CHECK_RUNS,
                                details={"run_id": run_id},
                            ),
                        }
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
    def get_summary(run_id: str, request: Request) -> SummaryResponse:
        try:
            r = runs.get(run_id)
        except KeyError:
            raise _http_error(
                request,
                status_code=404,
                code=ErrorCode.RUN_NOT_FOUND,
                message="run not found",
                hint=ErrorHint.CHECK_RUNS,
                details={"run_id": run_id},
            )
        if r.summary is None:
            if r.state in {"running", "starting"}:
                return SummaryResponse(
                    ok=False,
                    run_id=run_id,
                    error=ErrorDTO(
                        code=ErrorCode.RUN_STILL_RUNNING,
                        message="run still running",
                        hint=ErrorHint.RUN_STILL_RUNNING,
                        request_id=_request_id(request),
                    ),
                )
            return SummaryResponse(
                ok=False,
                run_id=run_id,
                error=ErrorDTO(
                    code=ErrorCode.SUMMARY_NOT_AVAILABLE,
                    message="summary not available",
                    hint=ErrorHint.SUMMARY_NOT_AVAILABLE,
                    request_id=_request_id(request),
                ),
            )
        return SummaryResponse(ok=True, run_id=run_id, summary=r.summary)

    @app.exception_handler(HTTPException)
    def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        rid = _request_id(request)
        payload = _coerce_http_error_detail(exc.detail, rid)
        return JSONResponse(
            status_code=exc.status_code,
            content={"ok": False, "error": payload},
            headers={"X-Request-ID": rid},
        )

    @app.exception_handler(Exception)
    def unhandled_exception_handler(request: Request, _: Exception) -> JSONResponse:
        rid = _request_id(request)
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": _error_payload(
                    code=ErrorCode.INTERNAL_ERROR,
                    message="internal server error",
                    request_id=rid,
                ),
            },
            headers={"X-Request-ID": rid},
        )

    return app
