# Contribuir a WhatsApp Tracking Assistant

## Desarrollo local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install black isort flake8 pytest-cov pre-commit
pre-commit install
pytest tests/ -q
```

## Estilo de código

- **Black** + **isort** (perfil black), longitud de línea **100** (`pyproject.toml`).
- **Flake8** con reglas en `.flake8` (imports tras `os.environ` en `conftest` / scripts: `E402` ignorado donde aplica).

## Dependencias delicadas

- **`bcrypt`**: no subir a **5.x** sin reemplazar o actualizar **passlib**; hoy `passlib[bcrypt]` 1.7.x falla con bcrypt 5 en CI y en local. Dependabot tiene `ignore` para major de bcrypt (ver `.github/dependabot.yml`).

## CI/CD (GitHub Actions)

Workflows en `.github/workflows/`:

| Archivo | Propósito |
|---------|-----------|
| `01-lint-and-format.yml` | black, isort, flake8, validación YAML |
| `02-tests.yml` | pytest + cobertura (SQLite en memoria, igual que tests locales) |
| `03-security.yml` | bandit, pip-audit, Trivy (filesystem) |
| `04-docker-build.yml` | build; push a `ghcr.io` solo en ramas protegidas / no-PR |
| `05-release.yml` | release al pushear tag `v*` |

**Badges en README:** usan el repo `lbertalot/whatsapp-tracking-assistant`. Si el remoto tiene otro `owner/name`, actualizá las URLs del escudo.

**Codecov (opcional):** secret `CODECOV_TOKEN` en el repo para informes en codecov.io; sin token el job de tests sigue pasando (`fail_ci_if_error: false`).

## Rama protegida (recomendado)

En GitHub → Settings → Branches → Branch protection para `main`:

- Require pull request antes de merge (1 revisión si el equipo lo usa).
- Require status checks: **Lint & Code Quality**, **Tests & Coverage** (y los que quieras volver obligatorios).
- Require branches up to date.

## Seguridad en GitHub

Habilitar donde aplique: Dependabot alerts, secret scanning, Dependabot security updates (`Settings → Code security and analysis`).

## Versionado

- Tags `v1.2.3` disparan `05-release.yml` (release en GitHub con extracto de `CHANGELOG.md` si existe).
