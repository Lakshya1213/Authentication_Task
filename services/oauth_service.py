"""
OAuth service — generalized business logic for login, callback, tokens, and disconnect across all providers.
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


class OAuthError(Exception):
    """Raised when OAuth or related persistence fails."""

    def __init__(self, message: str, error_type: str = "oauth_error") -> None:
        self.message = message
        self.error_type = error_type
        super().__init__(message)


class OAuthService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _get_provider_config(self, provider: str) -> dict:
        provider_key = provider.lower()
        if provider_key == "google":
            return {
                "client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret,
                "authorize_url": self.settings.google_authorize_url,
                "token_url": self.settings.google_token_url,
                "userinfo_url": self.settings.google_userinfo_url,
                "scopes": self.settings.google_scopes,
            }
        elif provider_key == "microsoft":
            return {
                "client_id": self.settings.microsoft_client_id,
                "client_secret": self.settings.microsoft_client_secret,
                "authorize_url": self.settings.microsoft_authorize_url,
                "token_url": self.settings.microsoft_token_url,
                "userinfo_url": self.settings.microsoft_userinfo_url,
                "scopes": self.settings.microsoft_scopes,
            }
        elif provider_key == "linkedin":
            return {
                "client_id": self.settings.linkedin_client_id,
                "client_secret": self.settings.linkedin_client_secret,
                "authorize_url": self.settings.linkedin_authorize_url,
                "token_url": self.settings.linkedin_token_url,
                "userinfo_url": self.settings.linkedin_userinfo_url,
                "scopes": self.settings.linkedin_scopes,
            }
        elif provider_key == "zoom":
            return {
                "client_id": self.settings.zoom_client_id,
                "client_secret": self.settings.zoom_client_secret,
                "authorize_url": self.settings.zoom_authorize_url,
                "token_url": self.settings.zoom_token_url,
                "userinfo_url": self.settings.zoom_userinfo_url,
                "scopes": self.settings.zoom_scopes,
            }
        else:
            raise OAuthError(f"Unsupported provider: {provider}", error_type="unsupported_provider")

    def build_authorization_url(self, provider: str, state: str, redirect_uri: str) -> str:
        """Build provider consent-screen URL for Authorization Code Flow."""
        config = self._get_provider_config(provider)
        if not config["client_id"] or not config["client_secret"]:
            raise OAuthError(
                f"{provider.capitalize()} integration is not configured on the server. "
                f"Please define {provider.upper()}_CLIENT_ID and {provider.upper()}_CLIENT_SECRET in the .env file.",
                error_type="configuration_error"
            )

        client = AsyncOAuth2Client(
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            redirect_uri=redirect_uri,
            scope=config["scopes"],
        )

        kwargs = {}
        if provider == "google":
            kwargs["access_type"] = "offline"
            kwargs["prompt"] = "consent"
        elif provider == "microsoft":
            kwargs["prompt"] = "consent"

        uri, _ = client.create_authorization_url(
            config["authorize_url"],
            state=state,
            **kwargs
        )
        logger.info("Generated %s authorization URL (redirect_uri=%s)", provider, redirect_uri)
        return uri

    async def exchange_code_for_tokens(self, provider: str, code: str, redirect_uri: str) -> dict:
        """Exchange authorization code for access and refresh tokens."""
        config = self._get_provider_config(provider)
        async with AsyncOAuth2Client(
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            redirect_uri=redirect_uri,
        ) as client:
            try:
                token = await client.fetch_token(
                    config["token_url"],
                    code=code,
                )
                logger.info("Successfully exchanged authorization code for %s tokens", provider)
                return token
            except Exception as exc:
                logger.exception("%s token exchange failed", provider)
                raise OAuthError(
                    f"Unable to exchange authorization code for {provider} tokens",
                    error_type="token_exchange_error",
                ) from exc

    async def fetch_user_profile(self, provider: str, access_token: str) -> dict:
        """Fetch user profile from provider userinfo endpoint."""
        config = self._get_provider_config(provider)
        async with httpx.AsyncClient() as client:
            try:
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(
                    config["userinfo_url"],
                    headers=headers,
                    timeout=10.0,
                )
                response.raise_for_status()
                profile = response.json()
                logger.info("Fetched %s profile", provider)
                return profile
            except Exception as exc:
                logger.exception("Failed to fetch %s profile", provider)
                raise OAuthError(
                    f"Unable to fetch user profile from {provider}",
                    error_type="profile_error",
                ) from exc

    def normalize_profile(self, provider: str, profile: dict) -> dict:
        """Normalize profile response formats from different providers."""
        provider_key = provider.lower()
        if provider_key == "google":
            email = profile.get("email")
            name = profile.get("name") or email
            picture = profile.get("picture")
        elif provider_key == "microsoft":
            email = profile.get("mail") or profile.get("userPrincipalName")
            name = profile.get("displayName") or email
            picture = None  # Fetching binary photo from Graph API is out of scope for basic profile
        elif provider_key == "linkedin":
            email = profile.get("email")
            name = profile.get("name") or f"{profile.get('given_name', '')} {profile.get('family_name', '')}".strip() or email
            picture = profile.get("picture")
        elif provider_key == "zoom":
            email = profile.get("email")
            name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip() or email
            picture = profile.get("pic_url")
        else:
            raise OAuthError(f"Unsupported provider: {provider}", error_type="unsupported_provider")

        if not email:
            raise OAuthError(f"{provider} profile is missing email", error_type="profile_error")

        return {
            "email": email,
            "name": name,
            "picture": picture,
        }

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

    def upsert_connected_account_and_tokens(
        self,
        db: Session,
        provider: str,
        user: User,
        token_data: dict,
    ) -> ConnectedAccount:
        """Create or update connected account and store encrypted tokens."""
        access_token = token_data.get("access_token")
        if not access_token:
            raise OAuthError("Missing access token in OAuth response", error_type="oauth_error")

        try:
            encrypted_access = encrypt_token(access_token)
            refresh_token = token_data.get("refresh_token")
            encrypted_refresh = encrypt_token(refresh_token) if refresh_token else None
        except ValueError as exc:
            raise OAuthError("Failed to encrypt OAuth tokens", error_type="encryption_error") from exc

        account = (
            db.query(ConnectedAccount)
            .filter(
                ConnectedAccount.user_id == user.id,
                ConnectedAccount.provider == provider,
            )
            .one_or_none()
        )

        config = self._get_provider_config(provider)

        if account is None:
            account = ConnectedAccount(
                user_id=user.id,
                provider=provider,
                status="connected",
                scopes=config["scopes"],
            )
            db.add(account)
            db.flush()
            logger.info("Created connected account id=%s for user id=%s and provider=%s", account.id, user.id, provider)
        else:
            account.status = "connected"
            account.scopes = config["scopes"]
            logger.info("Updated connected account id=%s for user id=%s and provider=%s", account.id, user.id, provider)

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

    def _parse_token_expiry(self, token_data: dict) -> datetime | None:
        expires_at = token_data.get("expires_at")
        if expires_at:
            return datetime.fromtimestamp(expires_at, tz=UTC)

        expires_in = token_data.get("expires_in")
        if expires_in:
            return datetime.now(tz=UTC) + timedelta(seconds=int(expires_in))

        return None

    async def handle_oauth_callback(
        self,
        db: Session,
        provider: str,
        code: str,
        redirect_uri: str,
        current_user_id: int | None = None,
    ) -> User:
        """
        Full callback pipeline: exchange code, fetch profile, persist user/tokens, and audit log.
        Supports primary login and secondary account connection.
        """
        try:
            token_data = await self.exchange_code_for_tokens(provider, code, redirect_uri)
            raw_profile = await self.fetch_user_profile(provider, token_data["access_token"])
            profile = self.normalize_profile(provider, raw_profile)

            # Resolve user
            user = None
            if current_user_id:
                user = db.query(User).filter(User.id == current_user_id).one_or_none()

            if user is None:
                # Primary sign-in / login: Find by email or create new
                email = profile["email"]
                user = db.query(User).filter(User.email == email).one_or_none()
                created = False
                if user is None:
                    user = User(
                        name=profile["name"],
                        email=email,
                        picture=profile["picture"],
                    )
                    db.add(user)
                    db.flush()
                    created = True
                    logger.info("Created new user id=%s email=%s via %s", user.id, user.email, provider)
                else:
                    user.name = profile["name"] or user.name
                    user.picture = profile["picture"] or user.picture
                    logger.info("Updated existing user id=%s email=%s via %s", user.id, user.email, provider)
            else:
                # Logged in account connection
                logger.info("Linking %s account to existing user id=%s", provider, user.id)

            # Upsert connection and tokens
            self.upsert_connected_account_and_tokens(db, provider=provider, user=user, token_data=token_data)

            # Logs
            self._create_audit_log(
                db,
                user_id=user.id,
                action="login" if not current_user_id else "connect",
                provider=provider,
                status="success",
            )

            db.commit()
            db.refresh(user)
            return user

        except OAuthError:
            db.rollback()
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Database error during OAuth callback")
            self._create_audit_log(
                db,
                user_id=current_user_id,
                action="failure",
                provider=provider,
                status="failed",
            )
            try:
                db.commit()
            except SQLAlchemyError:
                db.rollback()
            raise OAuthError("Database operation failed", error_type="database_error") from exc
        except Exception as exc:
            db.rollback()
            logger.exception("Unexpected error during OAuth callback")
            raise OAuthError("Unable to authenticate user", error_type="oauth_error") from exc

    def list_connected_apps(self, db: Session, user_id: int) -> list[ConnectedAccount]:
        """Return all connected accounts for a user."""
        return (
            db.query(ConnectedAccount)
            .filter(ConnectedAccount.user_id == user_id)
            .order_by(ConnectedAccount.created_at.desc())
            .all()
        )

    def disconnect_provider(self, db: Session, user_id: int, provider: str) -> None:
        """Mark provider account disconnected, delete tokens, and write audit log."""
        account = (
            db.query(ConnectedAccount)
            .filter(
                ConnectedAccount.user_id == user_id,
                ConnectedAccount.provider == provider,
            )
            .one_or_none()
        )

        if account is None:
            raise OAuthError(
                f"No connected {provider} account found for this user",
                error_type="not_found",
            )

        try:
            account.status = "disconnected"
            if account.oauth_token is not None:
                db.delete(account.oauth_token)

            self._create_audit_log(
                db,
                user_id=user_id,
                action="disconnect",
                provider=provider,
                status="success",
            )
            db.commit()
            logger.info("Disconnected %s account for user id=%s", provider, user_id)

        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Database error during disconnect")
            raise OAuthError("Database operation failed", error_type="database_error") from exc

    async def refresh_access_token(self, db: Session, user_id: int, provider: str) -> None:
        """
        Refresh expired access token using stored refresh token.
        Marks connection status as expired or failed if it fails.
        """
        account = (
            db.query(ConnectedAccount)
            .filter(
                ConnectedAccount.user_id == user_id,
                ConnectedAccount.provider == provider,
                ConnectedAccount.status == "connected",
            )
            .one_or_none()
        )

        if account is None or account.oauth_token is None:
            raise OAuthError(f"No active connection for {provider}", error_type="not_found")

        if not account.oauth_token.encrypted_refresh_token:
            account.status = "expired"
            self._create_audit_log(db, user_id=user_id, action="token_refresh", provider=provider, status="failed")
            db.commit()
            raise OAuthError("No refresh token available", error_type="oauth_error")

        try:
            refresh_token = decrypt_token(account.oauth_token.encrypted_refresh_token)
        except ValueError as exc:
            account.status = "failed"
            self._create_audit_log(db, user_id=user_id, action="token_refresh", provider=provider, status="failed")
            db.commit()
            raise OAuthError("Failed to decrypt refresh token", error_type="encryption_error") from exc

        config = self._get_provider_config(provider)

        async with AsyncOAuth2Client(
            client_id=config["client_id"],
            client_secret=config["client_secret"],
        ) as client:
            try:
                token_data = await client.refresh_token(
                    config["token_url"],
                    refresh_token=refresh_token,
                )
            except Exception as exc:
                account.status = "expired"
                self._create_audit_log(
                    db,
                    user_id=user_id,
                    action="token_refresh",
                    provider=provider,
                    status="failed",
                )
                db.commit()
                logger.exception("Token refresh failed for user id=%s provider=%s", user_id, provider)
                raise OAuthError("Token refresh failed", error_type="token_refresh_error") from exc

        try:
            encrypted_access = encrypt_token(token_data["access_token"])
            new_refresh = token_data.get("refresh_token")
            encrypted_refresh = encrypt_token(new_refresh) if new_refresh else None
        except ValueError as exc:
            account.status = "failed"
            db.commit()
            raise OAuthError("Failed to encrypt refreshed tokens", error_type="encryption_error") from exc

        account.oauth_token.encrypted_access_token = encrypted_access
        if encrypted_refresh:
            account.oauth_token.encrypted_refresh_token = encrypted_refresh
        account.oauth_token.expires_at = self._parse_token_expiry(token_data)

        self._create_audit_log(
            db,
            user_id=user_id,
            action="token_refresh",
            provider=provider,
            status="success",
        )
        db.commit()
        logger.info("Refreshed access token for user id=%s provider=%s", user_id, provider)


def get_oauth_service() -> OAuthService:
    """FastAPI dependency for the generalized OAuth service."""
    return OAuthService()
