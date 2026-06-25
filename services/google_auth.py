"""
Google OAuth service — business logic for login, callback, tokens, and disconnect.

Routes stay thin; this module owns Authlib integration, DB writes, and audit logging.
"""

import logging
from datetime import UTC, datetime, timedelta

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from config import Settings, get_settings
from models.audit_log import AuditLog
from models.connected_account import ConnectedAccount
from models.oauth_token import OAuthToken
from models.user import User
from utils.encryption import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

PROVIDER_GOOGLE = "google"
ACCOUNT_CONNECTED = "connected"
ACCOUNT_DISCONNECTED = "disconnected"

AUDIT_LOGIN = "login"
AUDIT_CONNECT = "connect"
AUDIT_DISCONNECT = "disconnect"
AUDIT_TOKEN_REFRESH = "token_refresh"
AUDIT_FAILURE = "failure"

AUDIT_SUCCESS = "success"
AUDIT_FAILED = "failed"


class GoogleAuthError(Exception):
    """Raised when Google OAuth or related persistence fails."""

    def __init__(self, message: str, error_type: str = "oauth_error") -> None:
        self.message = message
        self.error_type = error_type
        super().__init__(message)


class GoogleAuthService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def build_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Build Google consent-screen URL for Authorization Code Flow."""
        client = AsyncOAuth2Client(
            client_id=self.settings.google_client_id,
            client_secret=self.settings.google_client_secret,
            redirect_uri=redirect_uri,
            scope=self.settings.google_scopes,
        )
        uri, _ = client.create_authorization_url(
            self.settings.google_authorize_url,
            state=state,
            access_type="offline",
            prompt="consent",
        )
        logger.info("Generated Google authorization URL (redirect_uri=%s)", redirect_uri)
        return uri

    async def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> dict:
        """Exchange authorization code for access and refresh tokens."""
        async with AsyncOAuth2Client(
            client_id=self.settings.google_client_id,
            client_secret=self.settings.google_client_secret,
            redirect_uri=redirect_uri,
        ) as client:
            try:
                token = await client.fetch_token(
                    self.settings.google_token_url,
                    code=code,
                )
                logger.info("Successfully exchanged authorization code for tokens")
                return token
            except Exception as exc:
                logger.exception("Token exchange failed")
                raise GoogleAuthError(
                    "Unable to exchange authorization code for tokens",
                    error_type="token_exchange_error",
                ) from exc

    async def fetch_google_profile(self, access_token: str) -> dict:
        """Fetch user profile from Google userinfo endpoint."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    self.settings.google_userinfo_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10.0,
                )
                response.raise_for_status()
                profile = response.json()
                logger.info("Fetched Google profile for email=%s", profile.get("email"))
                return profile
            except Exception as exc:
                logger.exception("Failed to fetch Google profile")
                raise GoogleAuthError(
                    "Unable to fetch user profile from Google",
                    error_type="profile_error",
                ) from exc

    def _create_audit_log(
        self,
        db: Session,
        *,
        user_id: int | None,
        action: str,
        provider: str | None,
        status: str,
    ) -> None:
        log = AuditLog(
            user_id=user_id,
            action=action,
            provider=provider,
            status=status,
        )
        db.add(log)

    def get_or_create_user(self, db: Session, profile: dict) -> tuple[User, bool]:
        """Find user by email or create a new record from Google profile."""
        email = profile.get("email")
        if not email:
            raise GoogleAuthError("Google profile missing email", error_type="profile_error")

        user = db.query(User).filter(User.email == email).one_or_none()
        created = False

        if user is None:
            user = User(
                name=profile.get("name") or email,
                email=email,
                picture=profile.get("picture"),
            )
            db.add(user)
            db.flush()
            created = True
            logger.info("Created new user id=%s email=%s", user.id, user.email)
        else:
            user.name = profile.get("name") or user.name
            user.picture = profile.get("picture") or user.picture
            logger.info("Updated existing user id=%s email=%s", user.id, user.email)

        return user, created

    def _parse_token_expiry(self, token_data: dict) -> datetime | None:
        expires_at = token_data.get("expires_at")
        if expires_at:
            return datetime.fromtimestamp(expires_at, tz=UTC)

        expires_in = token_data.get("expires_in")
        if expires_in:
            return datetime.now(tz=UTC) + timedelta(seconds=int(expires_in))

        return None

    def upsert_connected_account_and_tokens(
        self,
        db: Session,
        *,
        user: User,
        token_data: dict,
    ) -> ConnectedAccount:
        """Create or update connected account and store encrypted tokens."""
        access_token = token_data.get("access_token")
        if not access_token:
            raise GoogleAuthError("Missing access token in OAuth response", error_type="oauth_error")

        try:
            encrypted_access = encrypt_token(access_token)
            refresh_token = token_data.get("refresh_token")
            encrypted_refresh = encrypt_token(refresh_token) if refresh_token else None
        except ValueError as exc:
            raise GoogleAuthError("Failed to encrypt OAuth tokens", error_type="encryption_error") from exc

        account = (
            db.query(ConnectedAccount)
            .filter(
                ConnectedAccount.user_id == user.id,
                ConnectedAccount.provider == PROVIDER_GOOGLE,
            )
            .one_or_none()
        )

        if account is None:
            account = ConnectedAccount(
                user_id=user.id,
                provider=PROVIDER_GOOGLE,
                status=ACCOUNT_CONNECTED,
                scopes=self.settings.google_scopes,
            )
            db.add(account)
            db.flush()
            logger.info("Created connected account id=%s for user id=%s", account.id, user.id)
        else:
            account.status = ACCOUNT_CONNECTED
            account.scopes = self.settings.google_scopes
            logger.info("Updated connected account id=%s for user id=%s", account.id, user.id)

        expires_at = self._parse_token_expiry(token_data)

        if account.oauth_token is None:
            oauth_token = OAuthToken(
                connected_account_id=account.id,
                encrypted_access_token=encrypted_access,
                encrypted_refresh_token=encrypted_refresh,
                expires_at=expires_at,
            )
            db.add(oauth_token)
        else:
            account.oauth_token.encrypted_access_token = encrypted_access
            if encrypted_refresh:
                account.oauth_token.encrypted_refresh_token = encrypted_refresh
            account.oauth_token.expires_at = expires_at

        logger.info("Stored encrypted OAuth tokens for connected account id=%s", account.id)
        return account

    async def handle_oauth_callback(
        self,
        db: Session,
        code: str,
        redirect_uri: str,
    ) -> User:
        """
        Full callback pipeline: exchange code, fetch profile, persist user/tokens, audit.
        """
        try:
            token_data = await self.exchange_code_for_tokens(code, redirect_uri)
            profile = await self.fetch_google_profile(token_data["access_token"])
            user, created = self.get_or_create_user(db, profile)
            self.upsert_connected_account_and_tokens(db, user=user, token_data=token_data)

            self._create_audit_log(
                db,
                user_id=user.id,
                action=AUDIT_LOGIN,
                provider=PROVIDER_GOOGLE,
                status=AUDIT_SUCCESS,
            )
            self._create_audit_log(
                db,
                user_id=user.id,
                action=AUDIT_CONNECT if created else AUDIT_CONNECT,
                provider=PROVIDER_GOOGLE,
                status=AUDIT_SUCCESS,
            )

            db.commit()
            db.refresh(user)
            return user

        except GoogleAuthError:
            db.rollback()
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Database error during OAuth callback")
            self._create_audit_log(
                db,
                user_id=None,
                action=AUDIT_FAILURE,
                provider=PROVIDER_GOOGLE,
                status=AUDIT_FAILED,
            )
            try:
                db.commit()
            except SQLAlchemyError:
                db.rollback()
            raise GoogleAuthError("Database operation failed", error_type="database_error") from exc
        except Exception as exc:
            db.rollback()
            logger.exception("Unexpected error during OAuth callback")
            raise GoogleAuthError("Unable to authenticate user", error_type="oauth_error") from exc

    def list_connected_apps(self, db: Session, user_id: int) -> list[ConnectedAccount]:
        """Return all connected accounts for a user."""
        return (
            db.query(ConnectedAccount)
            .filter(ConnectedAccount.user_id == user_id)
            .order_by(ConnectedAccount.created_at.desc())
            .all()
        )

    def disconnect_google(self, db: Session, user_id: int) -> None:
        """Mark Google account disconnected, delete tokens, write audit log."""
        account = (
            db.query(ConnectedAccount)
            .filter(
                ConnectedAccount.user_id == user_id,
                ConnectedAccount.provider == PROVIDER_GOOGLE,
            )
            .one_or_none()
        )

        if account is None:
            raise GoogleAuthError(
                "No connected Google account found for this user",
                error_type="not_found",
            )

        try:
            account.status = ACCOUNT_DISCONNECTED
            if account.oauth_token is not None:
                db.delete(account.oauth_token)

            self._create_audit_log(
                db,
                user_id=user_id,
                action=AUDIT_DISCONNECT,
                provider=PROVIDER_GOOGLE,
                status=AUDIT_SUCCESS,
            )
            db.commit()
            logger.info("Disconnected Google account for user id=%s", user_id)

        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Database error during disconnect")
            raise GoogleAuthError("Database operation failed", error_type="database_error") from exc

    async def refresh_access_token(self, db: Session, user_id: int) -> None:
        """
        Refresh expired access token using stored refresh token.

        Used internally when calling Google APIs; logs token_refresh audit events.
        """
        account = (
            db.query(ConnectedAccount)
            .filter(
                ConnectedAccount.user_id == user_id,
                ConnectedAccount.provider == PROVIDER_GOOGLE,
                ConnectedAccount.status == ACCOUNT_CONNECTED,
            )
            .one_or_none()
        )

        if account is None or account.oauth_token is None:
            raise GoogleAuthError("No active Google connection", error_type="not_found")

        if not account.oauth_token.encrypted_refresh_token:
            raise GoogleAuthError("No refresh token available", error_type="oauth_error")

        try:
            refresh_token = decrypt_token(account.oauth_token.encrypted_refresh_token)
        except ValueError as exc:
            self._create_audit_log(
                db,
                user_id=user_id,
                action=AUDIT_TOKEN_REFRESH,
                provider=PROVIDER_GOOGLE,
                status=AUDIT_FAILED,
            )
            db.commit()
            raise GoogleAuthError("Failed to decrypt refresh token", error_type="encryption_error") from exc

        async with AsyncOAuth2Client(
            client_id=self.settings.google_client_id,
            client_secret=self.settings.google_client_secret,
        ) as client:
            try:
                token_data = await client.refresh_token(
                    self.settings.google_token_url,
                    refresh_token=refresh_token,
                )
            except Exception as exc:
                self._create_audit_log(
                    db,
                    user_id=user_id,
                    action=AUDIT_TOKEN_REFRESH,
                    provider=PROVIDER_GOOGLE,
                    status=AUDIT_FAILED,
                )
                db.commit()
                logger.exception("Token refresh failed for user id=%s", user_id)
                raise GoogleAuthError("Token refresh failed", error_type="token_refresh_error") from exc

        try:
            encrypted_access = encrypt_token(token_data["access_token"])
            new_refresh = token_data.get("refresh_token")
            encrypted_refresh = encrypt_token(new_refresh) if new_refresh else None
        except ValueError as exc:
            raise GoogleAuthError("Failed to encrypt refreshed tokens", error_type="encryption_error") from exc

        account.oauth_token.encrypted_access_token = encrypted_access
        if encrypted_refresh:
            account.oauth_token.encrypted_refresh_token = encrypted_refresh
        account.oauth_token.expires_at = self._parse_token_expiry(token_data)

        self._create_audit_log(
            db,
            user_id=user_id,
            action=AUDIT_TOKEN_REFRESH,
            provider=PROVIDER_GOOGLE,
            status=AUDIT_SUCCESS,
        )
        db.commit()
        logger.info("Refreshed access token for user id=%s", user_id)


def get_google_auth_service() -> GoogleAuthService:
    """FastAPI dependency for the Google auth service."""
    return GoogleAuthService()
