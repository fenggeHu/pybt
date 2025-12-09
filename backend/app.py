import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import audit, auth, configs, data_sources, definitions, health, runs, users
from .services import init_db, rbac_service


def create_app() -> FastAPI:
    app = FastAPI(title="PyBT Web API", version="0.1.0")

    # Initialize database and default RBAC records
    init_db()
    rbac_service.ensure_seed_data()

    # 开发环境使用正则匹配本地地址，生产环境使用环境变量配置
    cors_origins = os.environ.get("CORS_ORIGINS", "").split(",") if os.environ.get("CORS_ORIGINS") else []
    # 匹配 localhost 和 127.0.0.1 的任意端口
    cors_origin_regex = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_origin_regex=cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    routers = [
        health.router,
        auth.router,
        definitions.router,
        data_sources.router,
        configs.router,
        audit.router,
        runs.router,
        users.router,
    ]
    for router in routers:
        app.include_router(router, prefix="/api")

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"service": "pybt-web", "version": "0.1.0"}

    return app


app = create_app()
