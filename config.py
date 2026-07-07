import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

from utils import ensure_directory, normalize_sqlite_uri, resolve_data_root

load_dotenv()


BASE_DIR = Path(__file__).parent.resolve()


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return int(value)


class Config:
    """Base configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable must be set")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable must be set")

    # Optional mail configuration for creator-request notifications.
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = _env_int("MAIL_PORT", 587)
    MAIL_USE_TLS = _env_bool("MAIL_USE_TLS", True)
    MAIL_USE_SSL = _env_bool("MAIL_USE_SSL", False)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER") or MAIL_USERNAME
    MODERATION_NOTIFICATION_EMAIL = (
        os.environ.get("MODERATION_NOTIFICATION_EMAIL")
        or os.environ.get("CREATOR_REQUEST_NOTIFICATION_EMAIL")
        or os.environ.get("admin_email")
    )
    CREATOR_REQUEST_NOTIFICATION_EMAIL = (
        os.environ.get("CREATOR_REQUEST_NOTIFICATION_EMAIL")
        or MODERATION_NOTIFICATION_EMAIL
        or os.environ.get("admin_email")
    )
    MODERATION_ENABLED = _env_bool("MODERATION_ENABLED", True)

    # Central data root for all generated data: db file, image files, backups.
    DATA_ROOT = resolve_data_root(os.environ.get("DATAROOT"), base_dir=BASE_DIR)
    RECIPE_IMAGE_DIR = ensure_directory(DATA_ROOT / "recipe")

    # Read DATABASE_URL if set, otherwise place SQLite DB in DATAROOT.
    raw_db = os.environ.get("DATABASE_URL")
    if not raw_db:
        raw_db = f"sqlite:///{(DATA_ROOT / 'recipes.db').as_posix()}"
    SQLALCHEMY_DATABASE_URI = normalize_sqlite_uri(raw_db, base_dir=BASE_DIR)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session configuration
    SESSION_TYPE = "filesystem"
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Flask-Login configuration
    REMEMBER_COOKIE_DURATION = timedelta(days=7)


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True
    SQLALCHEMY_ECHO = False
    # Allow fallback secret key for development only
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    SQLALCHEMY_ECHO = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
