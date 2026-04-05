from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite:///./dev.db"
    SECRET_KEY: str = "change-me-to-a-random-secret"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    WHATSAPP_API_URL: str = "https://graph.facebook.com/v25.0"
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    # MS-I07: firma con App Secret de Meta; verify token arbitrario en el portal
    META_APP_SECRET: str = ""
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: str = ""
    # True: sin token por tienda, usar WHATSAPP_ACCESS_TOKEN global (dev / single-tenant).
    # Prod multi-merchant: False + token por tienda (MS-I08).
    WHATSAPP_ALLOW_GLOBAL_FALLBACK: bool = True

    WEBHOOK_SECRET_TOKEN: str = "change-me"

    TIENDANUBE_APP_ID: str = ""
    TIENDANUBE_CLIENT_SECRET: str = ""
    # OAuth: scopes separados por espacio (ej. read_orders write_orders).
    # Vacío = URL sin parámetro scope (comportamiento previo).
    TIENDANUBE_OAUTH_SCOPE: str = ""
    TIENDANUBE_AUTH_URL: str = "https://www.tiendanube.com/apps/{app_id}/authorize"
    TIENDANUBE_TOKEN_URL: str = "https://www.tiendanube.com/apps/authorize/token"
    TIENDANUBE_API_URL: str = "https://api.tiendanube.com/v1"
    APP_BASE_URL: str = "http://localhost:8000"

    # Worker loop interval (seconds); override in Docker dev with POLL_INTERVAL_SECONDS=60
    POLL_INTERVAL_SECONDS: int = 300

    # Si no está vacío, GET /metrics exige cabecera X-Metrics-Key (despliegues públicos).
    METRICS_API_KEY: str = ""


settings = Settings()
