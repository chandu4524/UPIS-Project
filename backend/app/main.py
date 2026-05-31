from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.analytics_duckdb_api import router as analytics_duckdb_router
from app.api.assistant_api import router as assistant_router
from app.api.audit_api import router as audit_router
from app.api.reports_api import router as reports_router
from app.api.intelligence_search_api import router as intelligence_search_router
from app.api.ocr_api import router as ocr_router
from app.api.review_api import router as review_router
from app.api.template_mapping_api import router as template_mapping_router
from app.api.citizen_api import router as citizen_router
from app.api.dashboard_api import router as dashboard_router
from app.api.upload_api import router as upload_router
from app.api.bulk_upload_api import router as bulk_upload_router
from app.api.user_api import router as user_router
from app.api.users_admin_api import router as users_admin_router
from app.routes.staging_routes import router as staging_router
from app.routes.manual_review_routes_v2 import router as manual_review_v2_router
from app.routes.person360_routes import router as person360_router
from app.core.config import (
    APP_ENV,
    LOG_LEVEL,
    REQUEST_TIMEOUT_SECONDS,
    ensure_runtime_directories,
    log_config_summary,
)
from app.middleware.timeout_middleware import RequestTimeoutMiddleware
from app.services.demo_seed_service import verify_and_seed_demo_data
from app.services.duckdb_service import close_connection, initialize_duckdb
from app.services.health_service import get_health_status, log_startup_diagnostics
from app.core.exceptions import (
    http_exception_handler,
    validation_exception_handler,
)
from app.core.logging_config import get_logger, setup_logging
from app.database.connection import SessionLocal
from app.database.init_db import init_database
from app.models.citizen import Citizen
from app.utils.dependencies import get_db

logger = get_logger("gpip.startup")

setup_logging(LOG_LEVEL)
ensure_runtime_directories()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_config_summary(logger)
    log_startup_diagnostics(logger)
    logger.info("Initializing database…")
    init_database()
    db = SessionLocal()
    try:
        seed_result = verify_and_seed_demo_data(db)
        if any(seed_result.values()):
            logger.info("Demo data verification: %s", seed_result)
    finally:
        db.close()
    try:
        initialize_duckdb()
        logger.info("DuckDB analytics engine initialized")
    except Exception as exc:
        logger.warning("DuckDB initialization failed (analytics disabled): %s", exc)
    logger.info("GPIP backend ready")
    yield
    close_connection()
    logger.info("GPIP backend shutdown")


app = FastAPI(
    title="Government Person Intelligence Platform",
    description="Secure government intelligence portal API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestTimeoutMiddleware, timeout_seconds=REQUEST_TIMEOUT_SECONDS)

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "Unhandled error on %s %s: %s",
        request.method,
        request.url.path,
        exc,
    )
    message = (
        "An unexpected error occurred. Please try again shortly."
        if APP_ENV in ("production", "prod")
        else "An unexpected server error occurred."
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": message,
            "detail": None,
        },
    )

app.include_router(user_router)
app.include_router(users_admin_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(bulk_upload_router, prefix="/api")
app.include_router(staging_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(analytics_duckdb_router, prefix="/api")
app.include_router(citizen_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(template_mapping_router, prefix="/api")
app.include_router(review_router, prefix="/api")
app.include_router(manual_review_v2_router, prefix="/api")
app.include_router(person360_router, prefix="/api")
app.include_router(ocr_router, prefix="/api")
app.include_router(intelligence_search_router, prefix="/api")
app.include_router(assistant_router, prefix="/api")


@app.get("/")
def root():
    return {
        "success": True,
        "message": "GPIP Backend Running",
    }


@app.get("/api/health")
def health():
    """Deployment health — no authentication required."""
    db = None
    try:
        db = SessionLocal()
    except Exception as exc:
        logger.warning("Health check DB session failed: %s", exc)
    try:
        payload = get_health_status(db)
        status_code = 200 if payload.get("app_status") != "unhealthy" else 503
        return JSONResponse(status_code=status_code, content=payload)
    except Exception as exc:
        logger.exception("Health endpoint failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "app_status": "unhealthy",
                "database_status": "unknown",
                "environment": APP_ENV,
                "generated_at": None,
                "message": "Health check failed",
            },
        )
    finally:
        if db is not None:
            db.close()


@app.get("/api/db-check")
def db_check(db: Session = Depends(get_db)):
    citizen_count = db.query(Citizen).count()
    return {
        "success": True,
        "database": "connected",
        "citizen_count": citizen_count,
    }
