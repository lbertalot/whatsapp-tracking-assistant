# Preparación para piloto — Tiendanube + WhatsApp (tienda real)

Documento de **estado técnico y operativo** para el siguiente paso del proyecto: **una tienda real** con integración end-to-end **Tiendanube** (OAuth, webhooks, órdenes, datos de envío en payload/API) y **WhatsApp** (Meta Cloud API, plantillas, webhook de `statuses`, credenciales por tienda o fallback controlado).

- **Plan de hitos asociado**: `docs/MILESTONES.md` — **Track Piloto (MS-P01–MS-P05)**.
- **Checklists operativos complementarios**: `docs/META_GO_LIVE_CHECKLIST.md`, `docs/WHATSAPP_META.md`.
- **Fuente de verdad del estado de envío**: plataforma ecommerce (Tiendanube), vía webhooks + `fetch_order` + worker de reconciliación — **ADR-006**.

La **fuente de verdad** es el código; este documento resume hallazgos alineados al repo y se actualiza cuando cambie el comportamiento implementado.

### Migración y rollback (ecommerce como fuente de verdad — ADR-006)

**Prerrequisitos en producción:** `alembic upgrade head`; cada tienda que use sync debe tener **instalación Tiendanube activa** con `access_token` y onboarding activo.

**Datos legados:** órdenes en estado `ready_for_polling` pasan a `pending_tracking` (no a `in_transit`) para no asumir un envío confirmado sin una lectura coherente desde TN.

**Rollback:** `alembic downgrade` elimina columnas de sync/auditoría y puede **perder** flags como `ecommerce_sync_enabled` — no usar en producción sin backup de DB y plan acordado.

**Post-deploy:** revisar logs del worker (`TN sync fetch_order failed`, errores HTTP) y el panel para órdenes sin estado esperado.

---

## 1. Resumen ejecutivo

**Estado global: *Parcial* — apto para un piloto *controlado* de una tienda real, no para producción multi-merchant “sin checklist”.**

El código ya soporta el camino feliz: registro → OAuth Tiendanube con `state` → webhooks TN con HMAC y fetch de API → **worker de reconciliación** que consulta la **API de Tiendanube** (`fetch_order`) y aplica `map_tiendanube_order_detail` → motor de notificaciones con Graph API → webhook Meta firmado → panel y `StoreSettings` (plantillas, `whatsapp_enabled`, tokens).

Los **mayores riesgos del piloto** son **operativos y de configuración externa**: scopes y URLs de la **app en Tiendanube**, **cobertura de eventos** (no todas las tiendas publican tracking igual; puede hacer falta sondeo más frecuente o más webhooks), **plantillas Meta** (nombre, idioma, variables vs `whatsapp_include_body_params`), y que **`whatsapp_enabled` se crea en `false`** al registrarse — hay que activarlo en `/settings` o vía `PUT /api/settings`. En **`APP_ENV=development`** sin credenciales WA, `WhatsAppService.resolve_for_store` usa **mock**: el entorno del piloto debe usar **`production`** (o credenciales reales + fallback) para envíos reales.

---

## 2. Estado por área (referencia rápida)

| Área | Estado | Evidencia en código | Riesgo piloto |
|------|--------|---------------------|---------------|
| API + UI | Sí | `backend/app/main.py`, `api/ui.py` | Bajo |
| Auth JWT | Sí | `api/auth.py`, `core/dependencies.py` | Bajo |
| TN OAuth (panel + state) | Sí | `api/integrations.py`, `services/tiendanube.py` | **Bajo–Medio**: variable opcional `TIENDANUBE_OAUTH_SCOPE` en la URL; si vacía, igual que antes (scopes = app TN) |
| Webhooks TN | Sí | `api/webhooks_tn.py` | **Medio**: token/scopes; respuestas 503/200 según ADR-003 |
| Ecommerce / TN sync | Sí | `services/tiendanube_order_status.py`, `workers/polling.py` | **Medio**: forma del JSON TN vs expectativas; sin tracking en TN no hay mágia |
| Worker | Sí | `workers/polling.py` | **Bajo**: tiendas con `onboarding_status=active`, `ecommerce_sync_enabled=true`, instalación TN activa |
| WhatsApp | Sí | `services/whatsapp.py`, `services/notification.py`, `api/webhooks_whatsapp.py` | **Medio–Alto**: plantillas, `whatsapp_enabled`, Meta |
| Settings / panel stats | Sí | `api/settings.py` | Bajo |
| Observabilidad | Parcial | `api/health.py` | **Medio** si URL pública: opcional `METRICS_API_KEY` + cabecera `X-Metrics-Key` para proteger `/metrics` |
| Tests | Mocks | `tests/` (sin E2E contra TN/Meta reales) | Alto para confianza *sin* prueba manual |

---

## 3. Puntos fuertes

- Multi-tenant coherente (`store_id` en órdenes e intentos; JWT en panel).
- Onboarding TN con `state` acoplado al `Store` del usuario (**ADR-002**).
- Webhooks TN con payload mínimo + `fetch_order` / agregados (**ADR-003**).
- WhatsApp: credenciales por tienda + `WHATSAPP_ALLOW_GLOBAL_FALLBACK`, reintentos y códigos Graph conservadores; avisos de activación en onboarding/settings.
- Trazabilidad: `NotificationAttempt` + `provider_delivery_status` vía webhook Meta; `platform_status_raw` y `last_status_source` en órdenes para auditoría.
- Idempotencia: `store_id:order_id:event_type` en el motor de notificaciones.

---

## 4. Gaps y debilidades

**Técnicos**

- OAuth TN: sin `TIENDANUBE_OAUTH_SCOPE` en env, la URL sigue sin `scope=` (depende de la app TN).
- Tras registro: `whatsapp_enabled=False` — sin activar en panel, no hay envíos (avisos en onboarding/settings).
- `development` + sin credenciales → envíos WA en mock.
- `/metrics` sin `METRICS_API_KEY` sigue siendo público (definí la variable en prod público).

**Operativos / producto**

- Meta: App Review, Live, allowlist, UTILITY — ver `META_GO_LIVE_CHECKLIST.md`.
- Políticas TN / datos del comprador — revisar con negocio (LGPD Brasil y leyes locales; validar con asesor).

**Documentación**

- Alinear expectativas: scopes TN en consola de app; HMAC TN usa `TIENDANUBE_CLIENT_SECRET` en `webhooks_tn.py` (validar contra doc oficial TN).

---

## 5. Alineación código ↔ documentación

| Tema | Notas |
|------|--------|
| ADR-002 / ONB01, ADR-003 webhooks TN, ADR-004 registro, ADR-005 WhatsApp, **ADR-006** ecommerce como fuente de verdad | Coinciden con implementación actual. |
| MS-I03 en `MILESTONES.md` | Histórico: antes Weraha; hoy el hito equivalente es **sincronización TN / ecommerce** (ver sección MS-I03 actualizada). |
| OAuth `scope` | Opcional vía `TIENDANUBE_OAUTH_SCOPE`; si vacío, permisos = app TN. |
| `ecommerce_sync_enabled` vs worker | Alineado: worker solo elige tiendas con sync ecommerce activo e instalación TN. |

---

## 6. Checklist PRE-PILOTO — Tiendanube

- [ ] App TN (dev/staging) con `TIENDANUBE_APP_ID` y `TIENDANUBE_CLIENT_SECRET` iguales al servidor.
- [ ] Callback permitido: `{APP_BASE_URL}/integrations/tiendanube/callback` (HTTPS en prod).
- [ ] Scopes en la app TN suficientes para leer órdenes y registrar webhooks. Opcional: definir `TIENDANUBE_OAUTH_SCOPE` (p. ej. `read_orders write_orders`) para forzar el parámetro `scope` en la URL de autorización.
- [ ] Tras OAuth: `StoreInstallation` activa con token; `Store.external_store_id` = `user_id` TN.
- [ ] Webhooks apuntan a `{APP_BASE_URL}/webhooks/tiendanube` (registro vía `register_webhooks`; revisar logs si falla).
- [ ] Probar `order/created` o `order/paid` → orden persistida con teléfono / `invalid_phone`.
- [ ] Probar `order/fulfilled` → `tracking_number` según payload o API con `aggregates`.
- [ ] Verificar secreto usado para HMAC del webhook TN vs implementación (`TIENDANUBE_CLIENT_SECRET` en código).
- [ ] Flujo merchant: registro → login → install-url → callback → `onboarding_status` **active** (requisito del worker: `StoreSettings.onboarding_status == "active"`).
- [ ] `default_phone_region` en settings si los números vienen sin prefijo internacional (ISO alpha-2, p. ej. PY, AR, MX).

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
| **P0** | Ecommerce: confirmar que webhooks + worker reflejan `in_transit` / `delivered` según datos TN (sin courier externo). |
| **P1** | Webhook Meta en dominio final; revisar errores Graph. |
| **P1** | En prod público: definir `METRICS_API_KEY` y llamar `/metrics` con `X-Metrics-Key`. |
| **P2** | Copy onboarding, runbook tokens TN, plan App Review. |

---

## 9. Unknowns (decisión humana)

- Cobertura de eventos y tracking por tienda TN (variabilidad por merchant).
- Scopes efectivos de cada instalación TN.
- Política multi-merchant vs fallback global en el piloto.
- Calendario App Review y modo prueba vs Live.
- Opt-in / mensajes UTILITY según políticas aplicables (checklist producto, no asesoría legal).

---

## 10. Definición de hecho del piloto (DoD)

> **Un pedido real creado o pagado en la tienda Tiendanube vinculada genera una orden en WTA con teléfono válido y estado derivado de datos TN; el webhook y/o el worker de reconciliación reflejan al menos una transición a *en tránsito* y otra a *entregado* según `map_tiendanube_order_detail`; por cada transición elegible se envía la plantilla WhatsApp correspondiente al cliente real; en el panel el merchant ve la orden, los intentos y, si el webhook Meta está configurado, el estado de entrega actualizado en `NotificationAttempt`.**

---

## Cambios técnicos recientes (pilot readiness)

| Cambio | Detalle |
|--------|---------|
| **OAuth TN `scope`** | `TIENDANUBE_OAUTH_SCOPE` en `Settings` / env; `TiendanubeService.get_auth_url()` añade `scope=` si no está vacío. |
| **Aviso WhatsApp** | Bloques informativos en `onboarding.html` y `settings.html` (activar notificaciones y credenciales). |
| **Worker + ecommerce** | Reconciliación vía API TN cuando `ecommerce_sync_enabled` y onboarding activo; sin adaptador de courier en el núcleo (**ADR-006**). |
| **Panel** | Región telefónica por defecto (`default_phone_region`); sin toggles Weraha. |
| **`/metrics`** | Si `METRICS_API_KEY` está definido, exige cabecera `X-Metrics-Key` idéntica (comparación en tiempo constante). |
| **Webhook WA** | Test de regresión: POST sin firma con `META_APP_SECRET` configurado → 403. |

---

## Referencias de código (índice)

| Ruta | Rol |
|------|-----|
| `backend/app/main.py` | Routers montados |
| `backend/app/api/integrations.py` | OAuth TN + `install-url` |
| `backend/app/api/webhooks_tn.py` | Webhook TN |
| `backend/app/services/tiendanube.py` | Cliente HTTP TN |
| `backend/app/services/tiendanube_order_status.py` | Mapeo JSON TN → estado interno |
| `backend/app/workers/polling.py` | Worker de reconciliación TN |
| `backend/app/services/notification.py` | Motor de notificaciones |
| `backend/app/services/whatsapp.py` | Graph API + resolución por tienda |
| `backend/app/api/webhooks_whatsapp.py` | Webhook Meta |
| `backend/app/api/settings.py` | `GET/PUT /api/settings`, `/panel/stats` |
| `backend/app/api/health.py` | `/health`, `/ready`, `/metrics` |
| `backend/app/core/config.py` | Variables `Settings` |

---

*Última revisión alineada al repositorio WTA (FastAPI, PostgreSQL, worker).*
