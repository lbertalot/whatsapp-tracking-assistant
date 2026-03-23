from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


@router.get("/")
def root():
    return RedirectResponse(url="/login")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html")


@router.get("/panel", response_class=HTMLResponse)
def panel_page(request: Request):
    return templates.TemplateResponse(request, "orders.html")


@router.get("/onboarding", response_class=HTMLResponse)
def onboarding_page(request: Request):
    return templates.TemplateResponse(request, "onboarding.html")


@router.get("/ayuda/conectar-tiendanube", response_class=HTMLResponse)
def help_connect_tiendanube(request: Request):
    """Guía pública (sin login): cómo entrar al panel y qué necesita el vendedor."""
    return templates.TemplateResponse(request, "ayuda_conectar_tiendanube.html")


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return templates.TemplateResponse(request, "settings.html")
