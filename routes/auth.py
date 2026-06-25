"""
Authentication and connected-account HTTP routes.

Handles Google OAuth login/callback, listing connected apps, and disconnect.
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
from services.google_auth import GoogleAuthError, GoogleAuthService, get_google_auth_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

SESSION_USER_ID_KEY = "user_id"
SESSION_OAUTH_STATE_KEY = "oauth_state"
SESSION_OAUTH_REDIRECT_URI_KEY = "oauth_redirect_uri"
FRONTEND_HOME = "/"


def _oauth_redirect_uri(request: Request) -> str:
    """
    Build callback URL from the current request host.

    Ensures Google redirects back to the same host the user started on
    (localhost vs 127.0.0.1 are different cookie domains in browsers).
    """
    return str(request.url_for("google_oauth_callback"))


def _redirect_with_error(message: str, error_type: str = "oauth_error") -> RedirectResponse:
    """Send browser back to the frontend with an error query param."""
    params = f"error={quote(error_type)}&message={quote(message)}"
    return RedirectResponse(url=f"{FRONTEND_HOME}?{params}", status_code=status.HTTP_302_FOUND)


def _error_response(exc: GoogleAuthError, status_code: int) -> HTTPException:
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
                message="Not authenticated. Please log in with Google first.",
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


@router.get("/auth/google/login")
async def google_login(request: Request) -> RedirectResponse:
    """
    Redirect the browser to Google's OAuth consent screen.

    Uses Authorization Code Flow with a random state value for CSRF protection.
    """
    logger.info("Google login requested from host=%s", request.url.hostname)
    state = secrets.token_urlsafe(32)
    redirect_uri = _oauth_redirect_uri(request)

    request.session[SESSION_OAUTH_STATE_KEY] = state
    request.session[SESSION_OAUTH_REDIRECT_URI_KEY] = redirect_uri

    service = get_google_auth_service()
    authorization_url = service.build_authorization_url(state, redirect_uri)
    return RedirectResponse(url=authorization_url, status_code=status.HTTP_302_FOUND)


@router.get("/auth/google/callback", name="google_oauth_callback")
async def google_callback(
    request: Request,
    db: Session = Depends(get_db),
    service: GoogleAuthService = Depends(get_google_auth_service),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """
    Handle Google's redirect after user approves or denies consent.

    Exchanges the authorization code, stores user/tokens, establishes session,
    then redirects to the frontend dashboard.
    """
    logger.info("Google OAuth callback received")

    if error:
        logger.warning("Google OAuth error in callback: %s", error)
        return _redirect_with_error(f"Google OAuth denied: {error}")

    if not code:
        logger.warning("OAuth callback missing authorization code")
        return _redirect_with_error("Missing authorization code")

    saved_state = request.session.pop(SESSION_OAUTH_STATE_KEY, None)
    redirect_uri = request.session.pop(SESSION_OAUTH_REDIRECT_URI_KEY, None)

    if not saved_state or state != saved_state:
        logger.warning(
            "OAuth state mismatch — host=%s, has_session=%s",
            request.url.hostname,
            saved_state is not None,
        )
        return _redirect_with_error(
            "Invalid OAuth state parameter. "
            "Use the same URL for the whole flow (e.g. always http://127.0.0.1:8000)."
        )

    if not redirect_uri:
        logger.warning("OAuth redirect URI missing from session on host=%s", request.url.hostname)
        return _redirect_with_error("OAuth session expired. Please try logging in again.")

    try:
        user = await service.handle_oauth_callback(db, code, redirect_uri)
    except GoogleAuthError as exc:
        logger.warning("OAuth callback failed: %s", exc.message)
        return _redirect_with_error(exc.message, exc.error_type)

    request.session[SESSION_USER_ID_KEY] = user.id
    logger.info("OAuth callback succeeded for user id=%s", user.id)

    return RedirectResponse(
        url=f"{FRONTEND_HOME}?login=success",
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
    service: GoogleAuthService = Depends(get_google_auth_service),
) -> list[ConnectedAppResponse]:
    """Return connected OAuth providers and their status for the current user."""
    user_id = get_current_user_id(request)
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
    "/disconnect/google",
    response_model=DisconnectResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def disconnect_google(
    request: Request,
    db: Session = Depends(get_db),
    service: GoogleAuthService = Depends(get_google_auth_service),
) -> DisconnectResponse:
    """Disconnect Google account: mark disconnected, delete tokens, audit log."""
    user_id = get_current_user_id(request)
    logger.info("Disconnect Google requested for user id=%s", user_id)

    try:
        service.disconnect_google(db, user_id)
    except GoogleAuthError as exc:
        code = (
            status.HTTP_404_NOT_FOUND
            if exc.error_type == "not_found"
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        raise _error_response(exc, code) from exc

    request.session.pop(SESSION_USER_ID_KEY, None)

    return DisconnectResponse(message="Google account disconnected successfully")


@router.get("/me", response_model=UserSummary, responses={401: {"model": ErrorResponse}})
def get_me(
    request: Request,
    db: Session = Depends(get_db),
) -> UserSummary:
    """Return the currently authenticated user's profile (helper for POC testing)."""
    user_id = get_current_user_id(request)
    user = get_current_user(db, user_id)
    return UserSummary.model_validate(user)
