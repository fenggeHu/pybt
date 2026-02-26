import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .logging_config import setup_logging
from .router import bridge, router


setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Application startup completed, OpenD target=%s:%s", bridge.opend_host, bridge.opend_port)
    try:
        yield
    finally:
        logger.info("Application shutdown completed")


app = FastAPI(
    title="Futu Market Data Bridge",
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "FUTU",
            "description": "Futu OpenAPI 行情与订阅接口",
        }
    ],
)
app.include_router(router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.warning(
        "Request failed: method=%s path=%s status=%s detail=%s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, _exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: method=%s path=%s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal server error"})
