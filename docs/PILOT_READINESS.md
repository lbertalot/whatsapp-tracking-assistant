# Preparación para piloto — Tiendanube + WhatsApp (tienda real)

Documento de **estado técnico y operativo** para el siguiente paso del proyecto: **una tienda real** con integración end-to-end **Tiendanube** (OAuth, webhooks, órdenes, tracking) y **WhatsApp** (Meta Cloud API, plantillas, webhook de `statuses`, credenciales por tienda o fallback controlado).

- **Plan de hitos asociado**: `docs/MILESTONES.md` — **Track Piloto (MS-P01–MS-P05)**.
- **Checklists operativos complementarios**: `docs/META_GO_LIVE_CHECKLIST.md`, `docs/WHATSAPP_META.md`.

La **fuente de verdad** es el código; este documento resume hallazgos alineados al repo y se actualiza cuando cambie el comportamiento implementado.

---

## 1. Resumen ejecutivo

**Estado global: *Parcial* — apto para un piloto *controlado* de una tienda real, no para producción multi-merchant “sin checklist”.**

El código ya soporta el camino feliz: registro → OAuth Tiendanube con `state` → webhooks TN con HMAC y fetch de API → worker que consulta Weraha (HTTP real si `WERAHA_API_URL` es URL válida; si no, respuesta mock) → motor de notificaciones con Graph API → webhook Meta firmado → panel y `StoreSettings` (plantillas, `whatsapp_enabled`, tokens).

Los **mayores riesgos del piloto** son **operativos y de configuración externa**: scopes y URLs de la **app en Tiendanube**, **contrato real de Weraha** frente a `WerahaAdapter` (`GET …/tracking/{id}`), **plantillas Meta** (nombre, idioma, variables vs `whatsapp_include_body_params`), y que **`whatsapp_enabled` se crea en `false`** al registrarse — hay que activarlo en `/settings` o vía `PUT /api/settings`. En **`APP_ENV=development`** sin credenciales WA, `WhatsAppService.resolve_for_store` usa **mock**: el entorno del piloto debe usar **`production`** (o credenciales reales + fallback) para envíos reales.

---

## 2. Estado por área (referencia rápida)

| Área | Estado | Evidencia en código | Riesgo piloto |
|------|--------|---------------------|---------------|
| API + UI | Sí | `backend/app/main.py`, `api/ui.py` | Bajo |
| Auth JWT | Sí | `api/auth.py`, `core/dependencies.py` | Bajo |
| TN OAuth (panel + state) | Sí | `api/integrations.py`, `services/tiendanube.py` | **Medio**: `get_auth_url()` no añade `scope` — depende de la app TN |
| Webhooks TN | Sí | `api/webhooks_tn.py` | **Medio**: token/scopes; respuestas 503/200 según ADR-003 |
| Weraha | Parcial | `services/weraha.py`, `workers/polling.py` | **Alto** si API real ≠ contrato asumido; no usa `weraha_account_reference` por tienda |
| Worker | Sí | `workers/polling.py` | **Medio UX**: no filtra por `weraha_enabled` (flag informativo en panel) |
| WhatsApp | Sí | `services/whatsapp.py`, `services/notification.py`, `api/webhooks_whatsapp.py` | **Medio–Alto**: plantillas, `whatsapp_enabled`, Meta |
| Settings / panel stats | Sí | `api/settings.py` | Bajo |
| Observabilidad | Parcial | `api/health.py` (`/metrics` sin JWT, agregados globales) | **Medio** si URL pública |
| Tests | Mocks | `tests/` (sin E2E contra TN/Meta/Weraha reales) | Alto para confianza *sin* prueba manual |

---

## 3. Puntos fuertes

- Multi-tenant coherente (`store_id` en órdenes e intentos; JWT en panel).
- Onboarding TN con `state` acoplado al `Store` del usuario (**ADR-002**).
- Webhooks TN con payload mínimo + `fetch_order` / agregados (**ADR-003**).
- WhatsApp: credenciales por tienda + `WHATSAPP_ALLOW_GLOBAL_FALLBACK`, reintentos y códigos Graph conservadores.
- Trazabilidad: `NotificationAttempt` + `provider_delivery_status` vía webhook Meta.
- Idempotencia: `store_id:order_id:event_type` en el motor de notificaciones.

---

## 4. Gaps y debilidades

**Técnicos**

- Weraha: solo URL global + path fijo; `weraha_account_reference` no cableado al adapter.
- OAuth TN: sin parámetro `scope` en URL generada por código.
- Tras registro: `whatsapp_enabled=False` — sin activar, no hay envíos.
- `development` + sin credenciales → envíos WA en mock.
- `/metrics` público (sin auth).
- Worker no respeta `weraha_enabled` del modelo.

**Operativos / producto**

- Meta: App Review, Live, allowlist, UTILITY — ver `META_GO_LIVE_CHECKLIST.md`.
- Políticas TN / datos del comprador — revisar con negocio (LGPD base en webhooks).

**Documentación**

- Alinear expectativas: scopes TN en consola de app; HMAC TN usa `TIENDANUBE_CLIENT_SECRET` en `webhooks_tn.py` (validar contra doc oficial TN).

---

## 5. Alineación código ↔ documentación

| Tema | Notas |
|------|--------|
| ADR-002 / ONB01, ADR-003 webhooks TN, ADR-004 registro, ADR-005 WhatsApp | Coinciden con implementación actual. |
| MS-I03, MS-I05 en `MILESTONES.md` | Reflejan parcialidad Weraha y observabilidad. |
| OAuth `scope` | No está en `tiendanube.py` — documentar que los permisos vienen de la app TN. |
| `weraha_enabled` vs worker | Documentar o cambiar código en un milestone posterior. |

---

## 6. Checklist PRE-PILOTO — Tiendanube

- [ ] App TN (dev/staging) con `TIENDANUBE_APP_ID` y `TIENDANUBE_CLIENT_SECRET` iguales al servidor.
- [ ] Callback permitido: `{APP_BASE_URL}/integrations/tiendanube/callback` (HTTPS en prod).
- [ ] Scopes en la app TN suficientes para leer órdenes y registrar webhooks (el código no fija `scope` en la URL).
- [ ] Tras OAuth: `StoreInstallation` activa con token; `Store.external_store_id` = `user_id` TN.
- [ ] Webhooks apuntan a `{APP_BASE_URL}/webhooks/tiendanube` (registro vía `register_webhooks`; revisar logs si falla).
- [ ] Probar `order/created` o `order/paid` → orden persistida con teléfono / `invalid_phone`.
- [ ] Probar `order/fulfilled` → `tracking_number` según payload o API con `aggregates`.
- [ ] Verificar secreto usado para HMAC del webhook TN vs implementación (`TIENDANUBE_CLIENT_SECRET` en código).
- [ ] Flujo merchant: registro → login → install-url → callback → `onboarding_status` **active** (requisito del worker: `StoreSettings.onboarding_status == "active"`).

---

## 7. Checklist PRE-PILOTO — WhatsApp

- [ ] `APP_ENV` y credenciales: evitar modo mock involuntario (`development` sin token → mock en `resolve_for_store`).
- [ ] **Opción una tienda**: `WHATSAPP_ALLOW_GLOBAL_FALLBACK=true` + vars globales + **`whatsapp_enabled=true`** en la tienda (`auth.register` deja `False` por defecto).
- [ ] **Opción multi-tenant estricto**: fallback `false` + token y Phone Number ID en panel (`PUT /api/settings`).
- [ ] Plantillas aprobadas; nombres alineados a `template_in_transit` / `template_delivered` o defaults `shipping_in_transit_v1` / `shipping_delivered_v1`.
- [ ] `whatsapp_template_language` coherente con Meta (ej. `es` vs `es_AR`).
- [ ] Sin variables en plantilla → `whatsapp_include_body_params=false`.
- [ ] Webhook HTTPS: `{APP_BASE_URL}/webhooks/whatsapp`, verify token, `META_APP_SECRET` para firma.
- [ ] Suscripción con eventos que incluyan **statuses**.
- [ ] Prueba: envío real → `provider_message_id` → actualización vía POST webhook en `NotificationAttempt`.

---

## 8. Orden sugerido (semana del piloto)

| Prioridad | Tarea |
|-----------|--------|
| **P0** | Entorno: Postgres, migraciones, `SECRET_KEY`, `APP_BASE_URL`, web + worker. |
| **P0** | TN: OAuth tienda real, webhooks, orden de prueba en DB. |
| **P0** | WA: tokens + activar `whatsapp_enabled` + plantillas; prueba a número permitido. |
| **P0** | Weraha: URL/API key reales **o** decisión explícita de tracking solo desde TN hasta validar Weraha. |
| **P1** | Webhook Meta en dominio final; revisar errores Graph. |
| **P1** | Decidir exposición de `/metrics`. |
| **P2** | Copy onboarding, runbook tokens TN, plan App Review. |

---

## 9. Unknowns (decisión humana)

- Contrato Weraha en producción (URL, JSON, estados).
- Scopes efectivos de cada instalación TN.
- Política multi-merchant vs fallback global en el piloto.
- Calendario App Review y modo prueba vs Live.
- Opt-in / mensajes UTILITY según políticas aplicables (checklist producto, no asesoría legal).

---

## 10. Definición de hecho del piloto (DoD)

> **Un pedido real creado o pagado en la tienda Tiendanube vinculada genera una orden en WTA con tracking y teléfono válido; el worker refleja al menos una transición a *en tránsito* y otra a *entregado* (según Weraha o datos TN); por cada transición elegible se envía la plantilla WhatsApp correspondiente al cliente real; en el panel el merchant ve la orden, los intentos y, si el webhook Meta está configurado, el estado de entrega actualizado en `NotificationAttempt`.**

---

## Referencias de código (índice)

| Ruta | Rol |
|------|-----|
| `backend/app/main.py` | Routers montados |
| `backend/app/api/integrations.py` | OAuth TN + `install-url` |
| `backend/app/api/webhooks_tn.py` | Webhook TN |
| `backend/app/services/tiendanube.py` | Cliente HTTP TN |
| `backend/app/services/weraha.py` | Adapter Weraha |
| `backend/app/workers/polling.py` | Worker |
| `backend/app/services/notification.py` | Motor de notificaciones |
| `backend/app/services/whatsapp.py` | Graph API + resolución por tienda |
| `backend/app/api/webhooks_whatsapp.py` | Webhook Meta |
| `backend/app/api/settings.py` | `GET/PUT /api/settings`, `/panel/stats` |
| `backend/app/api/health.py` | `/health`, `/ready`, `/metrics` |
| `backend/app/core/config.py` | Variables `Settings` |

---

*Última revisión alineada al repositorio WTA (FastAPI, PostgreSQL, worker).*
