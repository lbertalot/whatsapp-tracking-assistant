from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite:///./dev.db"
    SECRET_KEY: str = "change-me-to-a-random-secret"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    WHATSAPP_API_URL: str = "https://graph.facebook.com/v21.0"
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""

    WERAHA_API_URL: str = ""
    WERAHA_API_KEY: str = ""

    WEBHOOK_SECRET_TOKEN: str = "change-me"

    TIENDANUBE_APP_ID: str = ""
    TIENDANUBE_CLIENT_SECRET: str = ""
    TIENDANUBE_AUTH_URL: str = "https://www.tiendanube.com/apps/{app_id}/authorize"
    TIENDANUBE_TOKEN_URL: str = "https://www.tiendanube.com/apps/authorize/token"
    TIENDANUBE_API_URL: str = "https://api.tiendanube.com/v1"
    APP_BASE_URL: str = "http://localhost:8000"


settings = Settings()
