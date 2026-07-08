"""FastAPI backend (FRONTEND.md) — REST API поверх существующего ядра abkit.
Точка входа: `uvicorn backend.main:app`. Streamlit (app.py) продолжает
работать независимо на /legacy (см. docker/README.md после R7) — оба
транспорта используют один и тот же auth/jobs/db слой и одну БД."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.errors import register_exception_handlers
from backend.routers import admin as admin_router
from backend.routers import audit as audit_router
from backend.routers import auth as auth_router
from backend.routers import datasets as datasets_router
from backend.routers import experiments as experiments_router


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Fail fast — то же самое требование, что и у Streamlit-версии (app.py
    # main(), DOCKER.md §3): без настоящего ABKIT_SECRET_KEY сервис не должен
    # подниматься вообще, а не падать на первом логине.
    from abkit.auth.tokens import get_secret_key

    get_secret_key()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="abkit API",
        version="0.1.0",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        lifespan=_lifespan,
    )

    register_exception_handlers(app)

    # Нужен только для локальной разработки фронта (vite dev server на другом
    # порту/origin) — в проде frontend и /api/* на одном origin через nginx
    # (FRONTEND.md §2), там CORS не участвует вообще.
    dev_origins = [o.strip() for o in os.environ.get("ABKIT_CORS_ORIGINS", "").split(",") if o.strip()]
    if dev_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=dev_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(auth_router.router, prefix="/api/v1")
    app.include_router(experiments_router.router, prefix="/api/v1")
    app.include_router(datasets_router.router, prefix="/api/v1")
    app.include_router(admin_router.router, prefix="/api/v1")
    app.include_router(audit_router.router, prefix="/api/v1")

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    return app


app = create_app()
