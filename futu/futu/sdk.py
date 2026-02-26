import importlib
import logging
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


REQUIRED_SYMBOLS = [
    "AuType",
    "KLType",
    "OpenQuoteContext",
    "RET_OK",
    "Session",
    "SubType",
    "StockQuoteHandlerBase",
    "CurKlineHandlerBase",
    "TickerHandlerBase",
]

logger = logging.getLogger(__name__)


def _is_sdk_module(module: ModuleType | None) -> bool:
    if module is None:
        return False
    return all(hasattr(module, name) for name in REQUIRED_SYMBOLS)


def _load_futu_sdk() -> Any:
    loaded = sys.modules.get("futu")
    if _is_sdk_module(loaded):
        return loaded

    project_root = Path(__file__).resolve().parents[1]
    removed_paths: list[str] = []
    for raw_path in list(sys.path):
        resolved = Path(raw_path or ".").resolve()
        if resolved == project_root:
            removed_paths.append(raw_path)
            sys.path.remove(raw_path)

    removed_local_module = None
    if loaded is not None and not _is_sdk_module(loaded):
        removed_local_module = loaded
        sys.modules.pop("futu", None)

    try:
        sdk = importlib.import_module("futu")
    except Exception as exc:
        logger.exception("Failed to import futu SDK package")
        raise RuntimeError(
            "failed to import futu SDK package. install dependency from requirements.txt first."
        ) from exc
    finally:
        if removed_local_module is not None:
            sys.modules["futu"] = removed_local_module
        for raw_path in reversed(removed_paths):
            sys.path.insert(0, raw_path)

    missing = [name for name in REQUIRED_SYMBOLS if not hasattr(sdk, name)]
    if missing:
        missing_text = ", ".join(missing)
        logger.error("Futu SDK module missing symbols: %s", missing_text)
        raise RuntimeError(
            "futu-api package not available or shadowed by local directory; "
            "install dependency from futu/requirements.txt first. "
            f"missing symbols: {missing_text}"
        )
    return sdk


_futu_sdk = _load_futu_sdk()

AuType = _futu_sdk.AuType
KLType = _futu_sdk.KLType
OpenQuoteContext = _futu_sdk.OpenQuoteContext
RET_OK = _futu_sdk.RET_OK
Session = _futu_sdk.Session
SubType = _futu_sdk.SubType
StockQuoteHandlerBase = _futu_sdk.StockQuoteHandlerBase
CurKlineHandlerBase = _futu_sdk.CurKlineHandlerBase
TickerHandlerBase = _futu_sdk.TickerHandlerBase
