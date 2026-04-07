from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from jbl_audit_api.api.router import router as api_router
from jbl_audit_api.core.config import Settings, get_settings
from jbl_audit_api.core.exceptions import ServiceError
from jbl_audit_api.db.bootstrap import seed_reference_data
from jbl_audit_api.db.session import build_engine, build_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    engine = build_engine(resolved_settings.database_url)

    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            seed_reference_data(session_factory)
            yield
        finally:
            engine.dispose()

    app = FastAPI(title=resolved_settings.app_name, lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    @app.exception_handler(ServiceError)
    async def handle_service_error(_, exc: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    app.include_router(api_router)
    return app


app = create_app()
