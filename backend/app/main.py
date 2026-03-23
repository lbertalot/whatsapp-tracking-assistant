import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.app.core.config import settings
from backend.app.api.health import router as health_router
from backend.app.api.auth import router as auth_router
from backend.app.api.orders import router as orders_router
from backend.app.api.integrations import api_tn_router, router as integrations_router
from backend.app.api.onboarding import router as onboarding_router
from backend.app.api.webhooks_tn import router as webhooks_tn_router
from backend.app.api.webhooks_whatsapp import router as webhooks_whatsapp_router
from backend.app.api.settings import router as settings_router
from backend.app.api.ui import router as ui_router

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="WhatsApp Tracking Assistant",
    description="Post-purchase tracking notifications for Paraguay merchants",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(health_router, tags=["health"])
app.include_router(auth_router, tags=["auth"])
app.include_router(orders_router, tags=["webhooks"])
app.include_router(integrations_router, tags=["integrations"])
app.include_router(api_tn_router)
app.include_router(onboarding_router)
app.include_router(webhooks_tn_router, tags=["webhooks-tn"])
app.include_router(webhooks_whatsapp_router, tags=["webhooks-whatsapp"])
app.include_router(settings_router, tags=["settings"])
app.include_router(ui_router, tags=["ui"])
