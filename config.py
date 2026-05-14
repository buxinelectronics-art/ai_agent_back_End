import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "fallback-dev-secret-key-change-me")

    # Build database URL — handle all postgres:// variants
    # and switch to psycopg3 driver
    _raw = os.environ.get("DATABASE_URL", "")
    if _raw:
        _raw = _raw.replace("postgres://", "postgresql://")
        if "postgresql+psycopg://" not in _raw:
            _raw = _raw.replace("postgresql://", "postgresql+psycopg://")
        # Strip sslmode and channel_binding from URL — pass via connect_args
        if "?" in _raw:
            _raw = _raw.split("?")[0]
    SQLALCHEMY_DATABASE_URI = _raw

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle":  300,
        "connect_args":  {
            "sslmode": "require",
        },
    }

    JWT_SECRET_KEY            = os.environ.get("JWT_SECRET_KEY", "fallback-dev-secret-key-change-me")
    JWT_ACCESS_TOKEN_EXPIRES  = timedelta(hours=8)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL   = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

    UPLOAD_FOLDER      = os.environ.get("UPLOAD_FOLDER",    "/var/data/uploads")
    GENERATED_FOLDER   = os.environ.get("GENERATED_FOLDER", "/var/data/generated")
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024

    ALLOWED_ORIGINS = os.environ.get(
        "ALLOWED_ORIGINS",
        "https://buxinelectronics-art.github.io,http://localhost:3000"
    ).split(",")

    DEFAULT_MIN_SCORE   = 70
    DEFAULT_DAILY_LIMIT = 50
