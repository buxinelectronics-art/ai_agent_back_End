import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "fallback-dev-secret")

    # Build DB URL — support psycopg3 dialect
    _db_url = os.environ["DATABASE_URL"]
    # Normalize any postgres:// prefix first
    _db_url = _db_url.replace("postgres://", "postgresql://")
    # Switch to psycopg3 driver
    if "postgresql+psycopg://" not in _db_url:
        _db_url = _db_url.replace("postgresql://", "postgresql+psycopg://")
    SQLALCHEMY_DATABASE_URI = _db_url

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle":  300,
    }

    JWT_SECRET_KEY            = os.environ.get("JWT_SECRET_KEY", "fallback-dev-secret")
    JWT_ACCESS_TOKEN_EXPIRES  = timedelta(hours=8)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
    GEMINI_MODEL   = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

    UPLOAD_FOLDER      = os.environ.get("UPLOAD_FOLDER",    "/var/data/uploads")
    GENERATED_FOLDER   = os.environ.get("GENERATED_FOLDER", "/var/data/generated")
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024

    ALLOWED_ORIGINS = os.environ.get(
        "ALLOWED_ORIGINS",
        "https://abdoukadir-ai.github.io,http://localhost:3000"
    ).split(",")

    DEFAULT_MIN_SCORE   = 70
    DEFAULT_DAILY_LIMIT = 50
