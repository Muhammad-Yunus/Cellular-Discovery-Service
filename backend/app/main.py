from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.config.settings import get_settings
from app.db.session import engine
from app.db.base import Base
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    generic_exception_handler,
)
from app.api.routers import scan, history, settings as settings_router, ws_gps, ws_scan
import logging

app_settings = get_settings()

logging.basicConfig(level=app_settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")
    yield
    logger.info("Shutting down application...")
    engine.dispose()


app = FastAPI(
    title="LTE Network Discovery API",
    description="USB Modem LTE Network Discovery Web Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

app.include_router(scan.router)
app.include_router(history.router)
app.include_router(settings_router.router)
app.include_router(ws_gps.router)
app.include_router(ws_scan.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
