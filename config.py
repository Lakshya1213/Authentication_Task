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

    # Microsoft settings
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None
    microsoft_authorize_url: str = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    microsoft_token_url: str = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    microsoft_userinfo_url: str = "https://graph.microsoft.com/v1.0/me"
    microsoft_scopes: str = "openid email profile User.Read"

    # LinkedIn settings (OIDC flow)
    linkedin_client_id: str | None = None
    linkedin_client_secret: str | None = None
    linkedin_authorize_url: str = "https://www.linkedin.com/oauth/v2/authorization"
    linkedin_token_url: str = "https://www.linkedin.com/oauth/v2/accessToken"
    linkedin_userinfo_url: str = "https://api.linkedin.com/v2/userinfo"
    linkedin_scopes: str = "openid profile email"

    # Zoom settings
    zoom_client_id: str | None = None
    zoom_client_secret: str | None = None
    zoom_authorize_url: str = "https://zoom.us/oauth/authorize"
    zoom_token_url: str = "https://zoom.us/oauth/token"
    zoom_userinfo_url: str = "https://api.zoom.us/v2/users/me"
    zoom_scopes: str = "user:read:user"
    zoom_redirect_uri: str | None = None

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
