import os


def test_settings_from_env():
    os.environ["DATABASE_URL"] = "postgresql://test:test@localhost/testdb"
    os.environ["SECRET_KEY"] = "my-test-secret"
    os.environ["APP_ENV"] = "testing"

    from backend.app.core.config import Settings

    settings = Settings()

    assert settings.DATABASE_URL == "postgresql://test:test@localhost/testdb"
    assert settings.SECRET_KEY == "my-test-secret"
    assert settings.APP_ENV == "testing"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 1440
    assert settings.LOG_LEVEL == "INFO"


def test_settings_has_all_required_fields():
    from backend.app.core.config import Settings

    settings = Settings()

    required = [
        "DATABASE_URL",
        "SECRET_KEY",
        "APP_ENV",
        "LOG_LEVEL",
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "WEBHOOK_SECRET_TOKEN",
    ]
    for field in required:
        assert hasattr(settings, field), f"Missing field: {field}"
