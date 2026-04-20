import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


BASE_DIR = Path(__file__).parent.parent.resolve()


def _normalize_sqlite_uri(uri: str) -> str:
    """Return an absolute-file SQLite URI for file-based SQLite URIs.

    - If `uri` is None, return None.
    - If uri is an in-memory DB or a non-sqlite URI, return it unchanged.
    - For `sqlite:///relative/path.db` produce an absolute-file uri
      `sqlite:////abs/path/to/relative/path.db` where the absolute path is
      resolved relative to the project `BASE_DIR`.
    """
    if not uri:
        return uri

    uri = str(uri)

    # Leave non-sqlite URIs and memory DBs unchanged
    if not uri.startswith("sqlite:") or uri.endswith(":memory:"):
        return uri

    # Absolute path: sqlite:////absolute/path.db -> keep as-is
    if uri.startswith("sqlite:////"):
        return uri

    # Relative path: sqlite:///relative/path.db -> resolve against BASE_DIR
    if uri.startswith("sqlite:///"):
        rel_path = uri[len("sqlite:///") :]
        abs_path = os.path.abspath(os.path.join(BASE_DIR, rel_path))

        # Ensure parent directory exists so SQLite can create the file
        parent = os.path.dirname(abs_path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)

        return f"sqlite:///{abs_path}"

    return uri


class Config:
    """Base configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable must be set")

    # Read the DATABASE_URL environment variable (or fallback) and normalize
    # file-based SQLite URIs to absolute paths to avoid accidental creation
    # of the DB in unexpected working directories (e.g. `instance/`).
    raw_db = os.environ.get("DATABASE_URL") or "sqlite:///recipes.db"
    SQLALCHEMY_DATABASE_URI = _normalize_sqlite_uri(raw_db)
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
