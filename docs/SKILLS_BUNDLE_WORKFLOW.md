# Flujo de skills (bundles) para Cursor — trazabilidad y ejecución

Este documento registra **qué bundle** usar en este repo, **en qué orden** conviene trabajar y **ejemplos de prompts** para mantener consistencia entre sesiones y agentes.

## Fuente de verdad del catálogo

| Elemento | Ubicación |
|----------|-----------|
| Lista editorial de bundles y skills | Instalación local: `docs/users/bundles.md` dentro de [antigravity-awesome-skills](https://github.com/sickn33/antigravity-awesome-skills) (p. ej. `~/.cursor/skills` o la ruta donde clonaste el repo de skills) |
| Producto y diseño del MVP | `docs/SPEC.md` |
| Milestones y criterios | `docs/MILESTONES.md` |
| Convenciones para agentes | `AGENTS.md` |
| Docker local | `docs/DOCKER.md` |
| Checklist de auditoría paso a paso | `docs/AUDIT_CHECKLIST.md` |

**Trazabilidad:** al planificar o revisar un cambio grande, citá en el PR o en la descripción del trabajo: *“alineado a `docs/SKILLS_BUNDLE_WORKFLOW.md`, fase X”*.

---

## Bundle seleccionado para este stack

Stack del proyecto: FastAPI, PostgreSQL, SQLAlchemy + Alembic, Jinja2 (sin React), pytest, Docker/Heroku, integraciones HTTP (Meta WhatsApp, Tiendanube, etc.).

| Prioridad | Bundle (nombre en `bundles.md`) | Uso en este repo |
|-----------|----------------------------------|------------------|
| Núcleo | **Python Pro** | FastAPI, async, pytest, patrones Python |
| Base | **Essentials** | Plan, calidad, git, debugging |
| Alta | **Security Developer** | APIs, JWT, OAuth/webhooks, backend seguro |
| Media | **QA & Testing** | TDD, revisión, arreglo de tests |
| Bajo (cuando toca infra) | **DevOps & Cloud** (recorte) | Docker, procedimientos de despliegue |

**No usar como base** para este monolito: *Web Wizard* / *Full-Stack Developer* del mismo catálogo (orientación React/Next/Node), salvo que el ADR del producto cambie.

---

## Cómo invocar skills en Cursor

- Referenciá skills con `@nombre-del-skill` (carpeta del skill en el repo de antigravity), por ejemplo `@fastapi-pro`.
- **Regla práctica:** 1 objetivo por hilo; **1–3 skills** por mensaje para no diluir el contexto.

---

## Fases de ejecución (orden recomendado)

Usá esta secuencia cuando el cambio toque varias capas (API + DB + tests + despliegue).

| Fase | Nombre | Skills típicos | Resultado esperado |
|------|--------|----------------|---------------------|
| 0 | Alcance | (lectura) `docs/SPEC.md`, `docs/MILESTONES.md` | Comportamiento y límites del MVP claros |
| 1 | Plan | `@concise-planning` | Supuestos, pasos, archivos, riesgos (multi-tenant `store_id`, idempotencia) |
| 2 | Implementación | `@fastapi-pro`, `@async-python-patterns`, `@python-patterns` | Código alineado al monolito existente |
| 3 | Persistencia | (opcional) `@postgres-best-practices` si está instalado | Consultas, índices, migraciones |
| 4 | Tests | `@python-testing-patterns`, `@test-driven-development` | pytest, mocks HTTP, fixtures DB |
| 5 | Seguridad | `@api-security-best-practices`, `@auth-implementation-patterns`, `@backend-security-coder` | Authz, webhooks, sin filtrar secretos en logs |
| 6 | UI servidor | `@frontend-security-coder` | Jinja: XSS, escape, enlaces |
| 7 | Calidad previa a PR | `@lint-and-validate`, `@code-review-checklist` | Lista de chequeo y comandos |
| 8 | Incidentes | `@systematic-debugging`, `@test-fixing` | Hipótesis, repro, fix mínimo |
| 9 | Entrega | `@git-pushing`, `@docker-expert`, `@deployment-procedures` | Commits, imagen local, Heroku |

---

## Prompts ejemplo por skill (plantillas en español)

Sustituí `[…]` por feature, rutas o mensajes de error reales.

### Essentials

- **`@concise-planning`** — *Quiero implementar [feature]. Enumerá supuestos, pasos mínimos, archivos a tocar y riesgos (DB, idempotencia, filtrado por store_id). Sin código aún.*
- **`@lint-and-validate`** — *Revisá coherencia de tipos, imports y uso de async en [archivos]; indicá comandos de validación acordes al repo.*
- **`@git-pushing`** — *Resumen de cambios: […]. Proponé mensaje de commit en inglés y si va un commit o varios.*
- **`@kaizen`** — *Tras [cambio], sugerí hasta 3 mejoras pequeñas de bajo riesgo sin ampliar el MVP.*
- **`@systematic-debugging`** — *Fallo: [log/trace]. Ordená hipótesis, qué instrumentar y cómo reproducir con tests.*

### Python Pro

- **`@python-pro`** — *En [módulo/función], aplicá buenas prácticas Python 3.12+ sin cambiar el contrato público.*
- **`@python-patterns`** — *Refactor idiomático mínimo de [código] sin cambiar comportamiento.*
- **`@fastapi-pro`** — *Diseñá o revisá [método ruta]: dependencias, códigos HTTP, esquemas Pydantic y errores.*
- **`@fastapi-templates`** — *Indicá en qué capa (api / services / db) debe vivir [lógica] en este monolito.*
- **`@python-testing-patterns`** — *Tests pytest para [caso]: fixtures, TestClient/async client, mocks httpx.*
- **`@async-python-patterns`** — *Revisá [código]: awaits, IO no bloqueante, sesiones DB async.*

### Security Developer

- **`@api-security-best-practices`** — *Threat model breve para [endpoint]: abuso, IDOR, validación de entrada.*
- **`@auth-implementation-patterns`** — *Revisá JWT/sesión: expiración, superficie de ataque, callbacks OAuth.*
- **`@backend-security-coder`** — *Revisá [módulo]: ORM seguro, httpx sin SSRF, logs sin tokens.*
- **`@frontend-security-coder`** — *Revisá [plantilla Jinja] contra XSS y enlaces inseguros.*
- **`@cc-skill-security-review`** — *Checklist de security review para el PR: authz por tienda y secretos.*

### QA & Testing

- **`@test-driven-development`** — *TDD para [feature]: tests que fallen primero según criterios de aceptación.*
- **`@code-review-checklist`** — *Revisión tipo reviewer: casos borde, tests, alineación con SPEC.*
- **`@test-fixing`** — *CI falla con: [output]. Causa raíz y corrección mínima.*

### DevOps & Cloud (cuando aplica)

- **`@docker-expert`** — *Revisá Dockerfile/compose: rebuild con cambios de plantillas, healthchecks, env.*
- **`@deployment-procedures`** — *Checklist de release: Alembic, Heroku release, verificación /health y /ready.*
- **`@environment-setup-guide`** — *Pasos breves para nuevo dev: entorno local equivalente a Heroku.*

---

## Prompts combinados frecuentes

1. **Feature API + tests:** `@concise-planning` `@fastapi-pro` `@python-testing-patterns` — *Feature [X]: plan corto, implementación, tests con mocks HTTP; todo scopeado por store_id.*
2. **Webhook / integración:** `@api-security-best-practices` `@backend-security-coder` `@python-testing-patterns` — *Webhook [X]: validación, idempotencia, logs seguros, tests.*
3. **OAuth / Tiendanube:** `@auth-implementation-patterns` `@api-security-best-practices` — *State, binding a store_id, TTL, respuestas 4xx claras.*
4. **Pre-merge:** `@lint-and-validate` `@code-review-checklist` `@cc-skill-security-review` — *Pase final antes de merge.*

---

## Mantenimiento de este documento

- Actualizar la tabla de fases o los bundles si el stack cambia (ver Parte III de `docs/SPEC.md`).
- Si se agregan skills nuevos al catálogo antigravity, incorporar solo los que aporten al MVP para no inflar el flujo.
