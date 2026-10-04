"""FastAPI application factory."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from premoulinette import __version__
from premoulinette.api import routes_analyses, routes_demo, routes_projects, routes_subjects, routes_system
from premoulinette.api.context import AppContext
from premoulinette.api.security import install_security
from premoulinette.api.services import ApiServices
from premoulinette.api.spa import mount_spa
from premoulinette.config import DEMO_DIR, FRONTEND_DIST, ensure_dirs
from premoulinette.engine.jobs import JobManager
from premoulinette.store.db import Store

log = logging.getLogger(__name__)


def create_app(
    data_dir: Path | None = None,
    store: Store | None = None,
    *,
    services: ApiServices | None = None,
    jobs: JobManager | None = None,
    frontend_dist: Path | None = None,
    demo_dir: Path | None = None,
) -> FastAPI:
    """Build the app. Every collaborator can be injected for tests; defaults use ``config``."""
    paths = ensure_dirs(data_dir)
    ctx = AppContext(
        paths=paths,
        store=store if store is not None else Store(paths.db),
        jobs=jobs if jobs is not None else JobManager(max_workers=2),
        services=services if services is not None else ApiServices(),
        demo_dir=demo_dir if demo_dir is not None else DEMO_DIR,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        ctx.jobs.shutdown(wait=False)

    app = FastAPI(
        title="PréMoulinette",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.ctx = ctx
    install_security(app)
    app.add_exception_handler(RequestValidationError, _validation_error)
    for module in (routes_system, routes_subjects, routes_projects, routes_analyses, routes_demo):
        app.include_router(module.router, prefix="/api")
    if mount_spa(app, frontend_dist if frontend_dist is not None else FRONTEND_DIST):
        log.info("Serving the frontend build from %s", frontend_dist or FRONTEND_DIST)
    return app


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    """422 with a compact ``{detail: [{loc, msg, type}]}`` (the rejected input is not echoed back)."""
    assert isinstance(exc, RequestValidationError)
    detail = [{"loc": list(e.get("loc", ())), "msg": e.get("msg", ""), "type": e.get("type", "")} for e in exc.errors()]
    return JSONResponse({"detail": detail}, status_code=422)
