"""
Application configuration loaded from environment variables.

Centralizes all settings so routes and services never read os.environ directly.
"""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env from the app directory before Settings is instantiated
load_dotenv(Path(__file__).resolve().parent / ".env")


class Settings(BaseSettings):
    """Typed configuration with defaults suitable for local development."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    google_client_id: str
    google_client_secret: str
    database_url: str
    secret_key: str
    fernet_key: str

    # Google OAuth endpoints (OpenID Connect discovery)
    google_authorize_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    google_token_url: str = "https://oauth2.googleapis.com/token"
    google_userinfo_url: str = "https://www.googleapis.com/oauth2/v3/userinfo"

    # Fallback default; login/callback derive the URI dynamically from the request host
    google_redirect_uri: str = "http://127.0.0.1:8000/auth/google/callback"

    # Basic profile scopes for POC — no Calendar/Gmail/etc.
    google_scopes: str = "openid email profile"

    app_name: str = "Google OAuth POC"
    debug: bool = True


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance (one parse per process)."""
    return Settings()
