import json
import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterable

import pandas as pd
from fastapi import HTTPException

from .sdk import (
    AuType,
    CurKlineHandlerBase,
    KLType,
    OpenQuoteContext,
    RET_OK,
    Session,
    StockQuoteHandlerBase,
    SubType,
    TickerHandlerBase,
)

logger = logging.getLogger(__name__)


class FutuBridge:
    def __init__(self) -> None:
        self.opend_host = os.getenv("FUTU_OPEND_HOST", "127.0.0.1")
        self.opend_port = int(os.getenv("FUTU_OPEND_PORT", "11111"))

    @staticmethod
    def parse_codes(codes: str) -> list[str]:
        values = [item.strip() for item in codes.split(",") if item.strip()]
        if not values:
            raise HTTPException(status_code=400, detail="codes cannot be empty")
        return values

    @staticmethod
    def parse_subtypes(subtypes: str) -> list[str]:
        values = [item.strip() for item in subtypes.split(",") if item.strip()]
        if not values:
            raise HTTPException(status_code=400, detail="subtypes cannot be empty")
        return values

    @staticmethod
    def enum_value(enum_cls: Any, name: str, field: str) -> Any:
        try:
            return getattr(enum_cls, name)
        except AttributeError as exc:
            logger.warning("Invalid enum value: field=%s value=%s", field, name)
            raise HTTPException(status_code=400, detail=f"invalid {field}: {name}") from exc

    @staticmethod
    def records(dataframe: pd.DataFrame | None) -> list[dict[str, Any]]:
        if dataframe is None or dataframe.empty:
            return []
        normalized = dataframe.where(pd.notnull(dataframe), None)
        return normalized.to_dict(orient="records")

    @staticmethod
    def ensure_ok(ret_code: int, payload: Any, action: str) -> None:
        if ret_code != RET_OK:
            logger.error("Futu API call failed: action=%s payload=%s", action, payload)
            raise HTTPException(status_code=502, detail=f"{action} failed: {payload}")

    @staticmethod
    def page_key_text(page_key: Any) -> str | None:
        if page_key is None:
            return None
        if isinstance(page_key, (bytes, bytearray)):
            return page_key.decode("utf-8", errors="ignore")
        return str(page_key)

    @staticmethod
    def sse_message(event: str, payload: dict[str, Any]) -> str:
        body = json.dumps(payload, ensure_ascii=False, default=str)
        return f"event: {event}\ndata: {body}\n\n"

    @staticmethod
    def _parse_bool(raw: str | None) -> bool | None:
        if raw is None:
            return None
        value = raw.strip().lower()
        if value in {"1", "true", "yes", "on"}:
            return True
        if value in {"0", "false", "no", "off"}:
            return False
        raise ValueError("FUTU_OPEND_IS_ENCRYPT must be true/false")

    def new_quote_context(self) -> OpenQuoteContext:
        is_encrypt_raw = os.getenv("FUTU_OPEND_IS_ENCRYPT")
        try:
            is_encrypt = self._parse_bool(is_encrypt_raw)
        except ValueError as exc:
            logger.error("Invalid FUTU_OPEND_IS_ENCRYPT value: %s", is_encrypt_raw)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        if is_encrypt is None:
            return OpenQuoteContext(host=self.opend_host, port=self.opend_port)
        return OpenQuoteContext(host=self.opend_host, port=self.opend_port, is_encrypt=is_encrypt)

    @contextmanager
    def quote_context(self) -> Iterable[OpenQuoteContext]:
        ctx = self.new_quote_context()
        try:
            yield ctx
        finally:
            ctx.close()

    def subscribe(
        self,
        ctx: OpenQuoteContext,
        codes: list[str],
        subtypes: list[Any],
        is_first_push: bool,
        subscribe_push: bool,
        session_value: Any,
    ) -> Any:
        try:
            return ctx.subscribe(
                codes,
                subtypes,
                is_first_push=is_first_push,
                subscribe_push=subscribe_push,
                session=session_value,
            )
        except TypeError:
            logger.debug("subscribe fallback without session argument")
            return ctx.subscribe(
                codes,
                subtypes,
                is_first_push=is_first_push,
                subscribe_push=subscribe_push,
            )

    def unsubscribe(self, ctx: OpenQuoteContext, codes: list[str], subtypes: list[Any], session_value: Any) -> Any:
        try:
            return ctx.unsubscribe(codes, subtypes, session=session_value)
        except TypeError:
            logger.debug("unsubscribe fallback without session argument")
            return ctx.unsubscribe(codes, subtypes)

    @staticmethod
    def history_kwargs(
        code: str,
        start: str | None,
        end: str | None,
        ktype: str,
        autype: str,
        max_count: int,
        page_req_key: Any,
        extended_time: bool,
        session: str,
    ) -> dict[str, Any]:
        return {
            "code": code,
            "start": start,
            "end": end,
            "ktype": FutuBridge.enum_value(KLType, ktype, "ktype"),
            "autype": FutuBridge.enum_value(AuType, autype, "autype"),
            "max_count": max_count,
            "page_req_key": page_req_key,
            "extended_time": extended_time,
            "session": FutuBridge.enum_value(Session, session, "session"),
        }

    @staticmethod
    def push_handler(subtype_name: str, push: Callable[[dict[str, Any]], None]) -> Any:
        if subtype_name == "QUOTE":
            base_cls = StockQuoteHandlerBase
        elif subtype_name == "TICKER":
            base_cls = TickerHandlerBase
        elif subtype_name.startswith("K_"):
            base_cls = CurKlineHandlerBase
        else:
            raise HTTPException(status_code=400, detail=f"subtype not supported for push bridge: {subtype_name}")

        class _Handler(base_cls):
            def on_recv_rsp(self, rsp_pb: Any):  # type: ignore[override]
                ret_code, data = super().on_recv_rsp(rsp_pb)
                payload = {
                    "type": subtype_name,
                    "at": int(time.time() * 1000),
                }
                if ret_code == RET_OK:
                    payload["rows"] = FutuBridge.records(data)
                else:
                    payload["error"] = str(data)
                    logger.warning("Push receive failed: subtype=%s error=%s", subtype_name, data)
                try:
                    push(payload)
                except Exception:
                    logger.exception("Push dispatch failed: subtype=%s", subtype_name)
                return ret_code, data

        return _Handler()


__all__ = [
    "AuType",
    "FutuBridge",
    "KLType",
    "Session",
    "SubType",
]
