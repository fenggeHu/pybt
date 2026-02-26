import asyncio
import logging
import time
from typing import Any, Iterable

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from .bridge import AuType, FutuBridge, KLType, Session, SubType


router = APIRouter(tags=["FUTU"])
bridge = FutuBridge()
logger = logging.getLogger(__name__)


@router.get("/healthz", summary="健康检查")
def healthz() -> dict[str, Any]:
    return {
        "status": "ok",
        "opend_host": bridge.opend_host,
        "opend_port": bridge.opend_port,
    }


@router.get("/quote/realtime/snapshot", summary="实时快照")
def realtime_snapshot(codes: str = Query(..., description="Comma separated symbols, e.g. SH.600000,SZ.000001")) -> dict[str, Any]:
    code_list = bridge.parse_codes(codes)
    with bridge.quote_context() as ctx:
        ret_code, data = ctx.get_market_snapshot(code_list)
        bridge.ensure_ok(ret_code, data, "get_market_snapshot")
        return {"codes": code_list, "rows": bridge.records(data)}


@router.get("/quote/realtime/stock", summary="实时行情(订阅后拉取)")
def realtime_stock_quote(
    codes: str = Query(..., description="Comma separated symbols"),
    session: str = Query("NONE", description="Session enum, e.g. NONE/RTH/ALL"),
) -> dict[str, Any]:
    code_list = bridge.parse_codes(codes)
    session_value = bridge.enum_value(Session, session, "session")
    with bridge.quote_context() as ctx:
        ret_code, sub_msg = bridge.subscribe(
            ctx=ctx,
            codes=code_list,
            subtypes=[SubType.QUOTE],
            is_first_push=False,
            subscribe_push=False,
            session_value=session_value,
        )
        bridge.ensure_ok(ret_code, sub_msg, "subscribe QUOTE")
        ret_code, data = ctx.get_stock_quote(code_list)
        bridge.ensure_ok(ret_code, data, "get_stock_quote")
        return {"codes": code_list, "rows": bridge.records(data)}


@router.get("/quote/realtime/kline", summary="实时K线(订阅后拉取)")
def realtime_kline(
    code: str = Query(..., description="Single symbol, e.g. SH.600000"),
    num: int = Query(30, ge=1, le=1000),
    ktype: str = Query("K_DAY", description="KLType enum"),
    autype: str = Query("QFQ", description="AuType enum"),
    session: str = Query("NONE", description="Session enum"),
) -> dict[str, Any]:
    ktype_value = bridge.enum_value(KLType, ktype, "ktype")
    autype_value = bridge.enum_value(AuType, autype, "autype")
    session_value = bridge.enum_value(Session, session, "session")
    subtype_value = bridge.enum_value(SubType, ktype, "subtype(derived from ktype)")
    with bridge.quote_context() as ctx:
        ret_code, sub_msg = bridge.subscribe(
            ctx=ctx,
            codes=[code],
            subtypes=[subtype_value],
            is_first_push=False,
            subscribe_push=False,
            session_value=session_value,
        )
        bridge.ensure_ok(ret_code, sub_msg, f"subscribe {ktype}")
        ret_code, data = ctx.get_cur_kline(code, num, ktype_value, autype_value)
        bridge.ensure_ok(ret_code, data, "get_cur_kline")
        return {"code": code, "rows": bridge.records(data)}


@router.get("/quote/subscription/query", summary="查看订阅状态")
def query_subscription(is_all_conn: bool = Query(False, description="Whether to query all OpenD connections")) -> dict[str, Any]:
    with bridge.quote_context() as ctx:
        try:
            ret_code, data = ctx.query_subscription(is_all_conn=is_all_conn)
        except TypeError:
            logger.debug("query_subscription fallback without is_all_conn argument")
            ret_code, data = ctx.query_subscription()
        bridge.ensure_ok(ret_code, data, "query_subscription")
        return {"rows": data}


@router.get("/quote/subscribe/sse", summary="订阅推送(SSE)")
async def subscribe_sse(
    request: Request,
    codes: str = Query(..., description="Comma separated symbols"),
    subtypes: str = Query("QUOTE", description="Comma separated SubType enums, e.g. QUOTE,K_1M"),
    is_first_push: bool = Query(True, description="Push cached first message from Futu"),
    session: str = Query("NONE", description="Session enum"),
    heartbeat_sec: int = Query(15, ge=3, le=60),
) -> StreamingResponse:
    code_list = bridge.parse_codes(codes)
    subtype_names = bridge.parse_subtypes(subtypes)
    subtype_values = [bridge.enum_value(SubType, name, "subtypes") for name in subtype_names]
    session_value = bridge.enum_value(Session, session, "session")

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=2000)

    def _enqueue_payload(payload: dict[str, Any]) -> None:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning("SSE queue is full, dropping payload")
        except Exception:
            logger.exception("Unexpected error while enqueuing SSE payload")

    def _push(payload: dict[str, Any]) -> None:
        try:
            loop.call_soon_threadsafe(_enqueue_payload, payload)
        except Exception:
            logger.exception("Failed to enqueue SSE payload")

    ctx = bridge.new_quote_context()
    for subtype_name in subtype_names:
        ctx.set_handler(bridge.push_handler(subtype_name, _push))

    try:
        ret_code, sub_msg = bridge.subscribe(
            ctx=ctx,
            codes=code_list,
            subtypes=subtype_values,
            is_first_push=is_first_push,
            subscribe_push=True,
            session_value=session_value,
        )
        bridge.ensure_ok(ret_code, sub_msg, "subscribe push")
        ctx.start()
    except Exception:
        logger.exception(
            "Failed to start SSE subscription: codes=%s subtypes=%s session=%s",
            code_list,
            subtype_names,
            session,
        )
        ctx.close()
        raise

    async def _stream() -> Iterable[str]:
        yield bridge.sse_message(
            "ready",
            {
                "codes": code_list,
                "subtypes": subtype_names,
                "session": session,
                "at": int(time.time() * 1000),
            },
        )
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=heartbeat_sec)
                    yield bridge.sse_message("quote", payload)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            try:
                bridge.unsubscribe(ctx, code_list, subtype_values, session_value)
            except Exception:
                logger.exception(
                    "Failed to unsubscribe SSE stream: codes=%s subtypes=%s session=%s",
                    code_list,
                    subtype_names,
                    session,
                )
            finally:
                ctx.close()

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.get("/quote/history/kline", summary="历史K线")
def history_kline(
    code: str = Query(..., description="Single symbol, e.g. SH.600000"),
    start: str | None = Query(None, description="YYYY-MM-DD"),
    end: str | None = Query(None, description="YYYY-MM-DD"),
    ktype: str = Query("K_DAY", description="KLType enum"),
    autype: str = Query("QFQ", description="AuType enum"),
    max_count: int = Query(1000, ge=1, le=1000),
    all_pages: bool = Query(False, description="Fetch all pages when true"),
    extended_time: bool = Query(False, description="Extended session for US market"),
    session: str = Query("NONE", description="Session enum"),
) -> dict[str, Any]:
    next_key: Any = None
    all_rows: list[dict[str, Any]] = []
    with bridge.quote_context() as ctx:
        while True:
            kwargs = bridge.history_kwargs(
                code=code,
                start=start,
                end=end,
                ktype=ktype,
                autype=autype,
                max_count=max_count,
                page_req_key=next_key,
                extended_time=extended_time,
                session=session,
            )
            try:
                ret_code, data, next_key = ctx.request_history_kline(**kwargs)
            except TypeError:
                logger.debug("request_history_kline fallback without session argument")
                kwargs.pop("session", None)
                ret_code, data, next_key = ctx.request_history_kline(**kwargs)
            bridge.ensure_ok(ret_code, data, "request_history_kline")
            all_rows.extend(bridge.records(data))
            if not all_pages or not next_key:
                break
    return {"code": code, "rows": all_rows, "next_page_req_key": bridge.page_key_text(next_key)}
