# Purpose: Centralized config helpers + environment loading for 91 CrPC

from __future__ import annotations
import os
from typing import Final
from dotenv import load_dotenv

load_dotenv()


# ---------- helpers ----------
def _get_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_int(key: str, default: int | None = None) -> int | None:
    val = os.getenv(key)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _get_list_csv(key: str) -> list[str]:
    val = os.getenv(key, "")
    items = [x.strip() for x in val.split(",") if x.strip()]
    return items


# ---------- app ----------
APP_NAME: str = os.getenv("APP_NAME", "91CrPC")
APP_ENV: str = os.getenv("APP_ENV", "development")  # development | staging | production
PORT: int | None = _get_int("PORT", 8000)
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
ENABLE_REQUEST_LOGS: bool = _get_bool("ENABLE_REQUEST_LOGS", True)
CORS_ALLOWED_ORIGINS: list[str] = _get_list_csv("CORS_ALLOWED_ORIGINS")


# ---------- security / auth ----------
SECRET_KEY: str | None = os.getenv("SECRET_KEY")
ACCESS_TOKEN_EXPIRE_MINUTES: int | None = _get_int("ACCESS_TOKEN_EXPIRE_MINUTES", 60)
REFRESH_TOKEN_EXPIRE_DAYS: int | None = _get_int("REFRESH_TOKEN_EXPIRE_DAYS", 30)
PASSWORD_HASH_SCHEME: str = os.getenv("PASSWORD_HASH_SCHEME", "bcrypt")


# ---------- mongodb ----------
# Either provide MONGO_URI directly or the components below to build one.
MONGO_URI: str = os.getenv("MONGO_URI", "").strip()
MONGO_USER: str = os.getenv("MONGO_USER", "").strip()
MONGO_PASSWORD: str = os.getenv("MONGO_PASSWORD", "").strip()
MONGO_CLUSTER: str = os.getenv("MONGO_CLUSTER", "").strip()  # e.g., "clustername.xxxxxx"
MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "").strip()

MONGO_MIN_POOL_SIZE: int | None = _get_int("MONGO_MIN_POOL_SIZE", 5)
MONGO_MAX_POOL_SIZE: int | None = _get_int("MONGO_MAX_POOL_SIZE", 50)
MONGO_CONN_TIMEOUT_MS: int | None = _get_int("MONGO_CONN_TIMEOUT_MS", 10000)
MONGO_SERVER_SELECTION_TIMEOUT_MS: int | None = _get_int("MONGO_SERVER_SELECTION_TIMEOUT_MS", 10000)
MONGO_TLS: bool = _get_bool("MONGO_TLS", True)


# ---------- redis / cache ----------
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL_SECONDS: int | None = _get_int("CACHE_TTL_SECONDS", 300)
ENABLE_CACHE: bool = _get_bool("ENABLE_CACHE", False)


# ---------- file storage ----------
MAX_UPLOAD_SIZE_MB: int | None = _get_int("MAX_UPLOAD_SIZE_MB", 10)
ALLOWED_FILE_TYPES: list[str] = _get_list_csv("ALLOWED_FILE_TYPES")  # e.g., "pdf,jpg,png"
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")


# ---------- azure blob storage ----------
AZURE_BLOB_CONN_STR: str | None = os.getenv("AZURE_BLOB_CONN_STR")
AZURE_BLOB_CONTAINER: str | None = os.getenv("AZURE_BLOB_CONTAINER")


# ---------- email / smtp ----------
SMTP_HOST: str | None = os.getenv("SMTP_HOST")
SMTP_PORT: int | None = _get_int("SMTP_PORT", 587)
SMTP_USERNAME: str | None = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD: str | None = os.getenv("SMTP_PASSWORD")
SMTP_USE_TLS: bool = _get_bool("SMTP_USE_TLS", True)
SMTP_FROM: str | None = os.getenv("SMTP_FROM")


# ---------- external integrations ----------
EXTERNAL_API_URL: str | None = os.getenv("EXTERNAL_API_URL")
EXTERNAL_API_KEY: str | None = os.getenv("EXTERNAL_API_KEY")


# ---------- api behavior / defaults ----------
PAGINATION_PAGE_SIZE_DEFAULT: int | None = _get_int("PAGINATION_PAGE_SIZE_DEFAULT", 25)
PAGINATION_PAGE_SIZE_MAX: int | None = _get_int("PAGINATION_PAGE_SIZE_MAX", 100)


# ---------- uri builders ----------
def build_mongo_uri() -> str:
    """
    Build a mongodb+srv URI from parts if MONGO_URI not provided.
    Example: mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority&appName=APP_NAME
    """
    if MONGO_URI:
        return MONGO_URI

    if not (MONGO_USER and MONGO_PASSWORD and MONGO_CLUSTER):
        raise RuntimeError(
            "Mongo configuration missing. Provide MONGO_URI or MONGO_USER, MONGO_PASSWORD, and MONGO_CLUSTER."
        )

    # Cluster should be the subdomain before .mongodb.net
    # Accept both "foo.bar" and full "foo.bar.mongodb.net" forms.
    host = MONGO_CLUSTER
    if not host.endswith(".mongodb.net"):
        host = f"{host}.mongodb.net"

    # Keep DB name out of URI; we select DB via client[db_name]
    return (
        f"mongodb+srv://{MONGO_USER}:{MONGO_PASSWORD}@{host}/"
        f"?retryWrites=true&w=majority&appName={APP_NAME}"
    )


# ---------- validation ----------
def validate_config() -> None:
    """
    Validate critical configuration on application startup.
    Raises RuntimeError if required settings are missing in production.
    """
    errors: list[str] = []

    # Critical security settings
    if not SECRET_KEY:
        errors.append("SECRET_KEY must be set")

    # Production-specific validations
    if APP_ENV == "production":
        if not CORS_ALLOWED_ORIGINS:
            errors.append("CORS_ALLOWED_ORIGINS must be configured in production")
        
        if not MONGO_URI and not all([MONGO_USER, MONGO_PASSWORD, MONGO_CLUSTER]):
            errors.append("MongoDB credentials required in production")
        
        if not MONGO_DB_NAME:
            errors.append("MONGO_DB_NAME must be set in production")

    # Database name validation
    if not MONGO_DB_NAME:
        errors.append("MONGO_DB_NAME must be set")

    if errors:
        error_msg = "\n  - ".join(["Configuration validation failed:"] + errors)
        raise RuntimeError(error_msg)


# ---------- startup check ----------
# Validate config on module import (can be disabled for testing)
if os.getenv("SKIP_CONFIG_VALIDATION", "").lower() not in {"1", "true", "yes"}:
    validate_config()
