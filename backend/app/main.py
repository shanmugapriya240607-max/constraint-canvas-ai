"""Application entry point for API foundation and authentication."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.auth import router as auth_router
from app.api.routes.plans import router as plans_router
from app.api.routes.health import router as health_router
from app.config import APP_NAME, APP_VERSION, SERVICE_NAME, Settings, settings
from app.database import SessionLocal, build_engine, engine, init_db
from app.schemas.common import MessageResponse, RootResponse
from app.services.security import TokenService, dummy_password_hash

logger = logging.getLogger(__name__)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Default validation errors can echo a submitted password/body in `input`.
    errors = [
        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled API exception", exc_info=(type(exc), exc, exc.__traceback__))
    payload = MessageResponse(status="error", message="An unexpected server error occurred.")
    return JSONResponse(status_code=500, content=payload.model_dump())


def create_app(config: Settings = settings, db_engine: Engine | None = None) -> FastAPI:
    if db_engine is None:
        db_engine = engine if config is settings else build_engine(config.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            init_db(db_engine)
            dummy_password_hash()
            yield
        finally:
            db_engine.dispose()

    application = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)
    application.state.token_service = TokenService(config)
    application.state.session_factory = (
        SessionLocal if db_engine is engine
        else sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=config.frontend_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    application.add_exception_handler(Exception, unhandled_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(plans_router)

    @application.get("/", response_model=RootResponse, tags=["root"])
    def root() -> RootResponse:
        return RootResponse(
            status="ok", message=SERVICE_NAME, version=APP_VERSION,
            docs="/docs", health="/api/health",
        )

    return application


app = create_app()
