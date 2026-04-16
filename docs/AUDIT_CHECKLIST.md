# Checklist de auditoría paso a paso — WhatsApp Post-Purchase Assistant

Uso: ejecutar en orden o por **hilos** (1 objetivo + 1–3 `@skills` por mensaje). Fuente de verdad de producto: `docs/SPEC.md`, `docs/MILESTONES.md`. Flujo de skills: `docs/SKILLS_BUNDLE_WORKFLOW.md`.

**Salida esperada por hallazgo:** severidad (P0 / P1 / P2), archivo o ruta, descripción breve, sugerencia de fix si aplica.

---

## Fase 0 — Alcance y trazabilidad

| # | Paso | Hecho cuando… |
|---|------|----------------|
| 0.1 | Leer Parte I de `docs/SPEC.md` (producto, flujos merchant/cliente). | Listás 3–5 comportamientos que el código **debe** cumplir en el MVP. |
| 0.2 | Cruzar con `docs/MILESTONES.md` (MS vigentes, criterios de aceptación). | Identificás qué partes del repo son **in scope** vs roadmap. |
| 0.3 | Anotar versión/stack desde `AGENTS.md` / `README.md`. | No hay supuestos contradictorios (p. ej. React, microservicios). |

**Skills sugeridos:** (solo lectura; opcional) `@code-review-checklist` para armar el marco del informe.

---

## Fase 1 — Mapa del monolito y rutas

| # | Paso | Hecho cuando… |
|---|------|----------------|
| 1.1 | Revisar `backend/app/main.py`: routers incluidos, middleware, CORS, static. | Tenés lista de prefijos de API y rutas HTML. |
| 1.2 | Inventariar `backend/app/api/*.py`: auth, orders, health, settings, onboarding, integrations, webhooks. | Cada módulo tiene anotado: auth requerida (sí/no), scope `store_id`. |
| 1.3 | Revisar `backend/app/api/ui.py` y templates enlazados. | Sabés qué páginas Jinja exponen datos de usuario/tienda. |

**Skills sugeridos:** `@concise-planning` (si falta documentar el mapa), `@fastapi-pro`.

---

## Fase 2 — Configuración y secretos

| # | Paso | Hecho cuando… |
|---|------|----------------|
| 2.1 | `backend/app/core/config.py` + `.env.example`: vars obligatorias, defaults inseguros. | No hay secretos hardcodeados; prod exige lo crítico. |
| 2.2 | Buscar en código: `print`, `logger` con tokens, `access_token` completo, passwords. | Logs y excepciones no filtran credenciales (ver ADR / SPEC). |
| 2.3 | URLs base (`APP_BASE_URL`, callbacks OAuth, webhooks): coherencia con SPEC. | Callbacks y redirects documentados o validados. |

**Skills sugeridos:** `@backend-security-coder`, `@varlock` (si usás gestión de env en local).

---

## Fase 3 — Autenticación y autorización

| # | Paso | Hecho cuando… |
|---|------|----------------|
| 3.1 | `backend/app/core/security.py`, `dependencies.py`: JWT, hash passwords, `get_current_user`. | Expiración, algoritmo y uso de `SECRET_KEY` son razonables. |
| 3.2 | `backend/app/api/auth.py`: login, logout, `/me`; rate limiting / errores genéricos si aplica MVP. | No hay bypass obvio; respuestas no filtran usuarios de otras tiendas. |
| 3.3 | **Todas** las rutas de negocio: ¿filtran por `store_id` del JWT? Revisar `orders`, `settings`, `onboarding`. | No hay IDOR entre merchants. |
| 3.4 | OAuth Tiendanube: `integrations.py`, callback, `state`, binding a `store_id` (MS-ONB01). | Flujo alineado a SPEC; conflictos 409 o política documentada. |

**Skills sugeridos:** `@auth-implementation-patterns`, `@api-security-best-practices`, `@cc-skill-security-review`.

---

## Fase 4 — API HTTP: validación, errores, contratos

| # | Paso | Hecho cuando… |
|---|------|----------------|
| 4.1 | Schemas Pydantic en `backend/app/schemas/`: campos requeridos, tipos, límites. | Entradas maliciosas o vacías no rompen el servidor sin 4xx claro. |
| 4.2 | Códigos HTTP coherentes (401/403/404/409/422) en auth, onboarding, integraciones. | Comportamiento documentado o predecible. |
| 4.3 | Clientes HTTP salientes (`httpx` en servicios): timeouts, manejo de errores, no SSRF por URLs controladas por usuario sin validación. | Llamadas a TN/Meta no bloquean indefinidamente. |

**Skills sugeridos:** `@fastapi-pro`, `@api-design-principles` (si dudás de REST), `@backend-security-coder`.

---

## Fase 5 — Webhooks e idempotencia

| # | Paso | Hecho cuando… |
|---|------|----------------|
| 5.1 | `webhooks_tn.py`: verificación de firma/secret, parsing, rechazo de payloads inválidos. | No se procesa webhook sin autenticación acordada en SPEC. |
| 5.2 | `webhooks_whatsapp.py`: validación Meta (HMAC u otra según implementación), duplicados. | Replays no generan efectos duplicados críticos. |
| 5.3 | Motor de notificaciones / `notification_attempts`: idempotencia por par clave (orden + estado + canal, según SPEC). | Reintentos no duplican envíos no deseados. |

**Skills sugeridos:** `@api-security-best-practices`, `@python-testing-patterns` (casos webhook).

---

## Fase 6 — Persistencia (SQLAlchemy + Alembic)

| # | Paso | Hecho cuando… |
|---|------|----------------|
| 6.1 | Modelos `backend/app/models/`: FK a `stores`, índices en campos de búsqueda frecuente. | Integridad referencial coherente con multi-tenant. |
| 6.2 | Migraciones `alembic/versions/` (raíz del repo): sin DROP destructivo no acordado; upgrade/downgrade razonable. | Historial revisado para cambios peligrosos. |
| 6.3 | Queries en servicios/API: N+1, filtros siempre con `store_id` donde corresponda. | No hay fugas de datos entre tiendas por query. |

**Skills sugeridos:** `@postgres-best-practices` (si está instalado), `@sql-optimization-patterns`.

---

## Fase 7 — Servicios de dominio y worker

| # | Paso | Hecho cuando… |
|---|------|----------------|
| 7.1 | `services/tiendanube*.py`, `state_mapper.py`, `tiendanube_order_status.py`: mapeo SPEC ↔ estados internos. | Transiciones y edge cases alineados a TN. |
| 7.2 | `services/whatsapp.py`, `notification.py`: plantillas, errores Meta, reintentos (1 retry + fail según SPEC). | Trazabilidad en DB de intentos. |
| 7.3 | `workers/polling.py`: ciclo seguro, manejo de errores, no bloqueo total si una tienda falla. | Worker observable (logs estructurados mínimos). |

**Skills sugeridos:** `@async-python-patterns`, `@observability-engineer` (recorte para logs).

---

## Fase 8 — UI servidor (Jinja2 + static)

| # | Paso | Hecho cuando… |
|---|------|----------------|
| 8.1 | `backend/app/templates/`: uso de `|e` donde haya datos no confiables; `autoescape` activo. | No hay XSS reflejado en panel/login/onboarding. |
| 8.2 | `static/js/`, enlaces externos, `target=_blank`: `rel` adecuado si aplica. | Copy y flujos alineados a español merchant. |
| 8.3 | Formularios y mensajes de error: accesibilidad mínima (labels, foco) si el MVP lo exige. | Lista P1/P2 de a11y si no es bloqueante. |

**Skills sugeridos:** `@frontend-security-coder`, `@fixing-accessibility` (si tocás HTML).

---

## Fase 9 — Tests y CI

| # | Paso | Hecho cuando… |
|---|------|----------------|
| 9.1 | `tests/`: cobertura de auth, orders scopeados, health, servicios críticos con mocks HTTP. | Gaps documentados (qué no está testeado y por qué). |
| 9.2 | Ejecutar `pytest` en raíz o `backend` según convención del repo. | Verde local; fallos clasificados. |
| 9.3 | Revisar workflows (`.github/workflows/`): mismo `pytest` que local; **Python** = versión de `.python-version`. **Formato:** `01-lint-and-format.yml` corre **black** + **isort** (check) + **flake8** (config `.flake8` / `pyproject.toml` según herramienta) + **pylint** informativo; en local, `pre-commit` o `pip install` como en ese job (ver `CONTRIBUTING.md`). | CI y entorno local reproducen lint/format. |

**Skills sugeridos:** `@python-testing-patterns`, `@test-fixing`, `@gha-security-review` (si hay Actions).

---

## Fase 10 — Cierre del informe y PR

| # | Paso | Hecho cuando… |
|---|------|----------------|
| 10.1 | Agrupar hallazgos: P0 (bloquea), P1 (antes de prod), P2 (mejora). | Cada ítem tiene ruta y criterio de cierre. |
| 10.2 | Cruzar hallazgos con `docs/SPEC.md` / `docs/MILESTONES.md` (¿bug vs fuera de alcance?). | No se “inventan” requisitos fuera del MVP sin ADR. |
| 10.3 | Pre-merge: linters/format del proyecto + revisión breve de diff. | Sin secretos en diff; commits en inglés si aplica `AGENTS.md`. |

**Skills sugeridos:** `@lint-and-validate`, `@code-review-checklist`, `@differential-review` o `@find-bugs` (cambios en rama).

---

## Plantilla rápida de registro de hallazgo

```text
[ID] P0|P1|P2 — Título corto
Archivo: backend/app/...
Evidencia: (línea, test que falla, o escenario)
Riesgo: (confidencialidad / integridad / disponibilidad / fraude)
Sugerencia: (fix mínimo o “documentar en SPEC”)
```

---

## Referencia de carpetas clave (backend)

| Área | Ruta |
|------|------|
| API | `backend/app/api/` |
| Core | `backend/app/core/` |
| Modelos | `backend/app/models/` |
| Servicios | `backend/app/services/` |
| Worker | `backend/app/workers/` |
| Templates | `backend/app/templates/` |
| Tests | `tests/` |

---

*Última alineación: flujo en `docs/SKILLS_BUNDLE_WORKFLOW.md`. Actualizar esta checklist si el stack o los milestones cambian.*
