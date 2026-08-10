from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from app.config.settings import get_settings
from app.db.session import engine
from app.db.base import Base
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    generic_exception_handler,
    validation_exception_handler,
)
from app.api.routers import scan, history, settings as settings_router, ws_gps, ws_scan, ws_mission, ws_device, mission_locations, missions, mission_planning, mission_control, mission_scans, device
from app.gps import test_management
import logging
from fastapi.middleware.cors import CORSMiddleware
from app.core.mission_executor import MissionExecutor
import os

app_settings = get_settings()

logging.basicConfig(level=app_settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")
    executor = MissionExecutor()
    await executor.startup()
    app.state.mission_executor = executor
    yield
    logger.info("Shutting down application...")
    await executor.shutdown()
    engine.dispose()


app = FastAPI(
    title="LTE Network Discovery API",
    description="USB Modem LTE Network Discovery Web Backend",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS Middleware
if app_settings.ALLOW_ALL_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
elif app_settings.ORIGIN_WHITELIST:
    origins = [origin.strip() for origin in app_settings.ORIGIN_WHITELIST.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Add exception handlers
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

app.include_router(scan.router)
app.include_router(history.router)
app.include_router(settings_router.router)
app.include_router(ws_gps.router)
app.include_router(ws_scan.router)
app.include_router(ws_mission.router)
app.include_router(mission_locations.router)
app.include_router(missions.router)
app.include_router(mission_planning.router)
app.include_router(mission_control.router)
app.include_router(mission_scans.router)
app.include_router(device.router)
app.include_router(ws_device.router)

# Test-only management endpoints — check env var at runtime so the import
# succeeds even if the server was already running before the env var was set.
if os.environ.get("TEST_MANAGEMENT_ENDPOINTS") == "1":
    test_management.attach(app)
    # Ensure mission_executor is available in app.state if lifespan wasn't triggered
    if not hasattr(app.state, "mission_executor"):
        from app.core.mission_executor import MissionExecutor
        app.state.mission_executor = MissionExecutor()
    logger.info("[TEST] Test management endpoints activated")


@app.get("/health")
def health_check():
    return {"status": "ok"}