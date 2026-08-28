import sys
import os
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from app.config.settings import get_settings
from app.db.session import engine
from app.db.base import Base
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    generic_exception_handler,
    validation_exception_handler,
)
from app.api.routers import scan, history, settings as settings_router, ws_gps, ws_scan, ws_mission, ws_device, mission_locations, missions, mission_planning, mission_control, mission_scans, device, device_status
from app.gps import test_management
from fastapi.middleware.cors import CORSMiddleware
from app.core.mission_executor import MissionExecutor

app_settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="LTE Network Discovery API",
    description="USB Modem LTE Network Discovery Web Backend",
    version="0.1.0",
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
app.include_router(device_status.router)

# Test-only management endpoints
if os.environ.get("TEST_MANAGEMENT_ENDPOINTS") == "1":
    test_management.attach(app)
    logger.info("[TEST] Test management endpoints activated")


@app.get("/health")
def health_check():
    return {"status": "ok"}


# ─── Startup logic (runs once when uvicorn starts) ───────────────────────────
async def _start_mission_executor():
    """Initialize MissionExecutor and restore any active missions."""
    executor = MissionExecutor()
    await executor.startup()
    app.state.mission_executor = executor
    logger.info("MissionExecutor started")


async def device_status_scheduler():
    """Background task to collect device status periodically."""
    from app.db.session import SessionLocal
    from app.core.device_collector import DeviceCollector

    interval = get_settings().DEVICE_STATUS_COLLECTION_INTERVAL
    logger.info(f"Device status scheduler started (interval: {interval}s)")

    # Collect immediately on startup
    try:
        with SessionLocal() as db:
            collector = DeviceCollector(db=db)
            await collector.collect_all()
        logger.info("Initial device status collection completed")
    except Exception as e:
        logger.error(f"Initial device status collection error: {e}")

    while True:
        await asyncio.sleep(interval)
        try:
            with SessionLocal() as db:
                collector = DeviceCollector(db=db)
                await collector.collect_all()
            logger.info("Device status collection completed")
        except asyncio.CancelledError:
            logger.info("Device status scheduler cancelled")
            break
        except Exception as e:
            logger.error(f"Device status collection error: {e}")


# Fire-and-forget both tasks at import time
loop = asyncio.get_event_loop()
loop.create_task(_start_mission_executor())
loop.create_task(device_status_scheduler())
