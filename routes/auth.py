"""
Authentication and connected-account HTTP routes.

Handles dynamic OAuth login/callback, listing connected apps, and disconnect for all providers.
"""

import logging
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from db.database import get_db
from models.user import User
from schemas.auth_schema import (
    ConnectedAppResponse,
    DisconnectResponse,
    ErrorResponse,
    UserSummary,
)
from services.oauth_service import OAuthError, OAuthService, get_oauth_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

SESSION_USER_ID_KEY = "user_id"
SESSION_OAUTH_STATE_KEY = "oauth_state"
SESSION_OAUTH_REDIRECT_URI_KEY = "oauth_redirect_uri"
FRONTEND_HOME = "/"


def _oauth_redirect_uri(request: Request, provider: str) -> str:
    """
    Build callback URL dynamically from the current request host and provider.

    Ensures the provider redirects back to the correct host and endpoint.
    """
    import os
    custom_uri = os.getenv(f"{provider.upper()}_REDIRECT_URI")
    if custom_uri:
        return custom_uri
    return str(request.url_for("oauth_callback", provider=provider))


def _redirect_with_error(message: str, error_type: str = "oauth_error") -> RedirectResponse:
    """Send browser back to the frontend with an error query param."""
    params = f"error={quote(error_type)}&message={quote(message)}"
    return RedirectResponse(url=f"{FRONTEND_HOME}?{params}", status_code=status.HTTP_302_FOUND)


def _error_response(exc: OAuthError, status_code: int) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=ErrorResponse(
            error_type=exc.error_type,
            message=exc.message,
        ).model_dump(),
    )


def get_current_user_id(request: Request) -> int:
    """Read authenticated user id from signed session cookie."""
    user_id = request.session.get(SESSION_USER_ID_KEY)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse(
                error_type="authentication_error",
                message="Not authenticated. Please log in first.",
            ).model_dump(),
        )
    return int(user_id)


def get_current_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse(
                error_type="authentication_error",
                message="User session is invalid.",
            ).model_dump(),
        )
    return user


@router.get("/auth/{provider}/login")
async def oauth_login(
    provider: str,
    request: Request,
    service: OAuthService = Depends(get_oauth_service),
) -> RedirectResponse:
    """
    Redirect the browser to the specified provider's OAuth consent screen.
    """
    logger.info("OAuth login requested for provider=%s", provider)
    original_state = secrets.token_urlsafe(32)
    redirect_uri = _oauth_redirect_uri(request, provider)

    # Encode user ID and original host in the state parameter to bridge domains
    current_user_id = request.session.get(SESSION_USER_ID_KEY)
    original_host = f"{request.url.scheme}://{request.url.netloc}"
    
    from utils.encryption import encrypt_token
    # Construct state payload: state|user_id|original_host|redirect_uri
    state_payload = f"{original_state}|{current_user_id or ''}|{original_host}|{redirect_uri}"
    encrypted_state = encrypt_token(state_payload)

    request.session[SESSION_OAUTH_STATE_KEY] = original_state
    request.session[SESSION_OAUTH_REDIRECT_URI_KEY] = redirect_uri

    try:
        authorization_url = service.build_authorization_url(provider, encrypted_state, redirect_uri)
        return RedirectResponse(url=authorization_url, status_code=status.HTTP_302_FOUND)
    except OAuthError as exc:
        return _redirect_with_error(exc.message, exc.error_type)


@router.get("/auth/{provider}/callback", name="oauth_callback")
async def oauth_callback(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
    service: OAuthService = Depends(get_oauth_service),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """
    Handle provider redirect after user consent. Matches code and handles user association.
    """
    logger.info("OAuth callback received for provider=%s", provider)

    if error:
        logger.warning("%s OAuth error in callback: %s", provider, error)
        return _redirect_with_error(f"{provider.capitalize()} OAuth denied: {error}")

    if not code:
        logger.warning("%s callback missing authorization code", provider)
        return _redirect_with_error("Missing authorization code")

    # Try decrypting the state to restore session context across domains
    original_state = None
    current_user_id = None
    original_host = FRONTEND_HOME
    redirect_uri = None

    if state:
        from utils.encryption import decrypt_token
        try:
            decrypted = decrypt_token(state)
            parts = decrypted.split("|")
            if len(parts) == 4:
                original_state = parts[0]
                user_id_str = parts[1]
                original_host = parts[2]
                redirect_uri = parts[3]
                if user_id_str:
                    current_user_id = int(user_id_str)
        except Exception:
            logger.warning("Failed to decrypt state parameter")

    # Fallback to session values if decryption failed
    saved_state = request.session.pop(SESSION_OAUTH_STATE_KEY, None)
    if not redirect_uri:
        redirect_uri = request.session.pop(SESSION_OAUTH_REDIRECT_URI_KEY, None)

    # Perform CSRF check: either decrypted state matches, or fallback to session state matches
    if original_state:
        # If successfully decrypted, it is signed by our server and secure
        pass
    elif not saved_state or state != saved_state:
        logger.warning(
            "OAuth state mismatch — provider=%s, host=%s, has_session=%s",
            provider,
            request.url.hostname,
            saved_state is not None,
        )
        return _redirect_with_error(
            "Invalid OAuth state parameter. "
            "Use the same URL for the whole flow (e.g. always http://127.0.0.1:8000)."
        )

    if not redirect_uri:
        logger.warning("OAuth redirect URI missing on host=%s", request.url.hostname)
        return _redirect_with_error("OAuth session expired. Please try logging in again.")

    if current_user_id:
        request.session[SESSION_USER_ID_KEY] = current_user_id
    else:
        current_user_id = request.session.get(SESSION_USER_ID_KEY)

    try:
        user = await service.handle_oauth_callback(
            db,
            provider=provider,
            code=code,
            redirect_uri=redirect_uri,
            current_user_id=current_user_id,
        )
    except OAuthError as exc:
        logger.warning("OAuth callback failed: %s", exc.message)
        return _redirect_with_error(exc.message, exc.error_type)

    request.session[SESSION_USER_ID_KEY] = user.id
    logger.info("OAuth callback succeeded for user id=%s via provider=%s", user.id, provider)

    return RedirectResponse(
        url=f"{original_host}?login=success",
        status_code=status.HTTP_302_FOUND,
    )


@router.get(
    "/connected-apps",
    response_model=list[ConnectedAppResponse],
    responses={401: {"model": ErrorResponse}},
)
def list_connected_apps(
    request: Request,
    db: Session = Depends(get_db),
    service: OAuthService = Depends(get_oauth_service),
) -> list[ConnectedAppResponse]:
    """Return connected OAuth providers and their status for the current user."""
    user_id = get_current_user_id(request)
    
    # Auto-connect HubSpot if static service key is defined in settings
    from config import get_settings
    settings = get_settings()
    if settings.hubspot_access_token:
        from models.connected_account import ConnectedAccount
        existing = db.query(ConnectedAccount).filter(
            ConnectedAccount.user_id == user_id,
            ConnectedAccount.provider == "hubspot"
        ).one_or_none()
        if not existing or existing.status != "connected":
            from models.user import User
            user = db.query(User).filter(User.id == user_id).one_or_none()
            if user:
                token_data = {
                    "access_token": settings.hubspot_access_token,
                    "refresh_token": None,
                    "expires_in": 315360000  # 10 years
                }
                service.upsert_connected_account_and_tokens(db, "hubspot", user, token_data)
                db.commit()
                
    accounts = service.list_connected_apps(db, user_id)

    return [
        ConnectedAppResponse(
            provider=account.provider,
            status=account.status,
            scopes=account.scopes,
            connected_at=account.created_at,
        )
        for account in accounts
    ]


@router.post(
    "/disconnect/{provider}",
    response_model=DisconnectResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def disconnect_provider(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
    service: OAuthService = Depends(get_oauth_service),
) -> DisconnectResponse:
    """Disconnect account for provider: mark status, delete tokens, audit log."""
    user_id = get_current_user_id(request)
    logger.info("Disconnect %s requested for user id=%s", provider, user_id)

    try:
        service.disconnect_provider(db, user_id, provider)
    except OAuthError as exc:
        code = (
            status.HTTP_404_NOT_FOUND
            if exc.error_type == "not_found"
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        raise _error_response(exc, code) from exc

    # Log out user if they have disconnected their last remaining active connection
    active_accounts = service.list_connected_apps(db, user_id)
    has_other_active = any(acc.status == "connected" for acc in active_accounts)
    if not has_other_active:
        request.session.pop(SESSION_USER_ID_KEY, None)

    return DisconnectResponse(message=f"{provider.capitalize()} account disconnected successfully")


@router.get("/me", response_model=UserSummary, responses={401: {"model": ErrorResponse}})
def get_me(
    request: Request,
    db: Session = Depends(get_db),
) -> UserSummary:
    """Return the currently authenticated user's profile."""
    user_id = get_current_user_id(request)
    user = get_current_user(db, user_id)
    return UserSummary.model_validate(user)
