"""
Webhook de WhatsApp Cloud API (Meta): verificación GET y eventos POST firmados.
Ver MS-I07 en docs/MILESTONES.md.
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.notification import NotificationAttempt
from backend.app.services.whatsapp import verify_meta_webhook_signature

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/webhooks/whatsapp")
def whatsapp_webhook_verify(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    expected = (settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Webhook verify token no configurado")
    if hub_mode == "subscribe" and hub_verify_token == expected:
        return PlainTextResponse(content=hub_challenge or "")
    raise HTTPException(status_code=403, detail="Verification failed")


def _apply_status_updates(db: Session, payload: dict) -> int:
    """Recorre entry/changes/value/statuses y actualiza NotificationAttempt por wamid. Retorna cantidad actualizada."""
    updated = 0
    if payload.get("object") != "whatsapp_business_account":
        return 0
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            for st in value.get("statuses") or []:
                mid = st.get("id")
                status = st.get("status")
                if not mid or not status:
                    continue
                ts_raw = st.get("timestamp")
                at: Optional[datetime] = None
                if ts_raw is not None:
                    try:
                        at = datetime.utcfromtimestamp(int(ts_raw))
                    except (ValueError, TypeError):
                        pass
                row = (
                    db.query(NotificationAttempt)
                    .filter(NotificationAttempt.provider_message_id == mid)
                    .first()
                )
                if row:
                    row.provider_delivery_status = status
                    if at:
                        row.provider_delivery_status_at = at
                    updated += 1
    if updated:
        db.commit()
    return updated


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook_event(request: Request, db: Session = Depends(get_db)):
    secret = (settings.META_APP_SECRET or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="META_APP_SECRET no configurado")

    body = await request.body()
    sig = request.headers.get("X-Hub-Signature-256")
    if not verify_meta_webhook_signature(body, sig, secret):
        logger.warning("WhatsApp webhook rechazado: firma inválida o ausente")
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload: dict[str, Any] = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON")

    n = _apply_status_updates(db, payload)
    if n:
        logger.info("WhatsApp webhook: %s intent(s) actualizados por estado de entrega", n)

    return {"success": True}
