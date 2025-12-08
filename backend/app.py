from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import audit, auth, configs, data_sources, definitions, health, runs


def create_app() -> FastAPI:
    app = FastAPI(title="PyBT Web API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
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
    ]
    for router in routers:
        app.include_router(router, prefix="/api")

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"service": "pybt-web", "version": "0.1.0"}

    return app


app = create_app()
