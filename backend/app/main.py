import logging

from fastapi import FastAPI

from backend.app.core.config import settings
from backend.app.api.health import router as health_router

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="WhatsApp Tracking Assistant",
    description="Post-purchase tracking notifications for Paraguay merchants",
    version="0.1.0",
)

app.include_router(health_router, tags=["health"])
