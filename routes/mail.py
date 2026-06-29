import logging
import re
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from routes.auth import get_current_user_id
from schemas.auth_schema import ErrorResponse
from schemas.mail_schema import (
    NormalizedMail,
    MailDraftCreate,
    MailDraftResponse,
    MailSendRequest,
    MailSendResponse,
    MailReplyRequest,
    MailReplyResponse
)
from services.mail_service import MailService, get_mail_service
from services.oauth_service import OAuthError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mail", tags=["mail"])


class SendDraftRequest(BaseModel):
    draft_id: str
    provider: str = "gmail"


def _handle_oauth_error(exc: OAuthError) -> HTTPException:
    """Map OAuthError to appropriate HTTPException for mail endpoints."""
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.error_type == "connection_missing":
        status_code = status.HTTP_400_BAD_REQUEST
    elif exc.error_type == "api_error":
        status_code = status.HTTP_502_BAD_GATEWAY
    elif exc.error_type == "token_refresh_failed":
        status_code = status.HTTP_401_UNAUTHORIZED
    elif exc.error_type == "unsupported_provider":
        status_code = status.HTTP_400_BAD_REQUEST

    return HTTPException(
        status_code=status_code,
        detail=ErrorResponse(
            error_type=exc.error_type,
            message=exc.message,
        ).model_dump(),
    )


@router.get(
    "/search",
    response_model=list[NormalizedMail],
    responses={401: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def search_emails(
    request: Request,
    query: str | None = Query(None, description="Search query/filter (e.g. from:customer@example.com)"),
    limit: int = Query(10, ge=1, le=50, description="Max messages to return"),
    provider: str = Query("gmail", description="Mail provider (gmail)"),
    db: Session = Depends(get_db),
    mail_service: MailService = Depends(get_mail_service),
) -> list[NormalizedMail]:
    """Search and retrieve emails matching the given query."""
    user_id = get_current_user_id(request)
    try:
        emails = await mail_service.search_messages(db, user_id, query, limit, provider)
        return emails
    except OAuthError as exc:
        raise _handle_oauth_error(exc) from exc


@router.get(
    "/read",
    response_model=NormalizedMail,
    responses={401: {"model": ErrorResponse}, 400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def read_email(
    request: Request,
    message_id: str = Query(..., description="The unique ID of the email message"),
    provider: str = Query("gmail", description="Mail provider (gmail)"),
    db: Session = Depends(get_db),
    mail_service: MailService = Depends(get_mail_service),
) -> NormalizedMail:
    """Get full details and body content of a specific email."""
    user_id = get_current_user_id(request)
    try:
        email = await mail_service.read_message(db, user_id, message_id, provider)
        return email
    except OAuthError as exc:
        raise _handle_oauth_error(exc) from exc


@router.post(
    "/draft",
    response_model=MailDraftResponse,
    responses={401: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def create_email_draft(
    request: Request,
    draft_data: MailDraftCreate,
    db: Session = Depends(get_db),
    mail_service: MailService = Depends(get_mail_service),
) -> MailDraftResponse:
    """Create a new email draft."""
    user_id = get_current_user_id(request)
    try:
        res = await mail_service.create_draft(
            db,
            user_id=user_id,
            to=draft_data.to,
            cc=draft_data.cc,
            subject=draft_data.subject,
            body=draft_data.body,
            provider=draft_data.provider or "gmail"
        )
        return MailDraftResponse(draft_id=res["draft_id"], status=res["status"])
    except OAuthError as exc:
        raise _handle_oauth_error(exc) from exc


@router.post(
    "/send",
    response_model=MailSendResponse,
    responses={401: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def send_email(
    request: Request,
    send_data: MailSendRequest,
    db: Session = Depends(get_db),
    mail_service: MailService = Depends(get_mail_service),
) -> MailSendResponse:
    """Send an email. If confirmation_required is True, creates a draft and requires confirmation."""
    user_id = get_current_user_id(request)
    try:
        res = await mail_service.send_message(
            db,
            user_id=user_id,
            to=send_data.to,
            cc=send_data.cc,
            subject=send_data.subject,
            body=send_data.body,
            provider=send_data.provider or "gmail",
            confirmation_required=send_data.confirmation_required
        )
        return MailSendResponse(
            status=res["status"],
            draft_id=res.get("draft_id"),
            message=res.get("message")
        )
    except OAuthError as exc:
        raise _handle_oauth_error(exc) from exc


@router.post(
    "/reply",
    response_model=MailReplyResponse,
    responses={401: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def reply_to_email(
    request: Request,
    reply_data: MailReplyRequest,
    db: Session = Depends(get_db),
    mail_service: MailService = Depends(get_mail_service),
) -> MailReplyResponse:
    """Reply to an existing email thread (creates a draft reply)."""
    user_id = get_current_user_id(request)
    try:
        res = await mail_service.reply_to_message(
            db,
            user_id=user_id,
            message_id=reply_data.message_id,
            body=reply_data.body,
            provider=reply_data.provider
        )
        return MailReplyResponse(
            status=res["status"],
            draft_id=res.get("draft_id"),
            message_id=res.get("message_id")
        )
    except OAuthError as exc:
        raise _handle_oauth_error(exc) from exc


@router.post(
    "/send-draft",
    response_model=MailSendResponse,
    responses={401: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def send_email_draft(
    request: Request,
    payload: SendDraftRequest,
    db: Session = Depends(get_db),
    mail_service: MailService = Depends(get_mail_service),
) -> MailSendResponse:
    """Send an existing draft email (used for explicit confirmation workflow)."""
    user_id = get_current_user_id(request)
    try:
        res = await mail_service.send_draft(
            db,
            user_id=user_id,
            draft_id=payload.draft_id,
            provider=payload.provider
        )
        return MailSendResponse(
            status=res["status"],
            message=res.get("message")
        )
    except OAuthError as exc:
        raise _handle_oauth_error(exc) from exc


def parse_natural_language_email_query(query_str: str) -> dict:
    """
    Parse email search or compose intent from a natural language query.
    Returns a dictionary of action parameters.
    """
    q_lower = query_str.lower().strip()
    
    # 1. Match Compose / Draft intent
    # Matches: "draft/send/write/create email to user@test.com with subject hello and body this is test"
    # Matches: "draft a follow-up email to customer@example.com"
    draft_match = re.match(
        r'(?:draft|send|write|create)\s+(?:an?\s+)?(?:email\s+)?to\s+(\S+@\S+|\S+)(?:\s+with\s+subject\s+([^-]+))?(?:\s+with\s+body\s+(.+))?',
        query_str,
        re.IGNORECASE
    )
    
    if draft_match:
        to_email = draft_match.group(1).strip()
        to_email = re.sub(r'[<>\'"]', '', to_email)
        
        subject = draft_match.group(2) or ""
        body = draft_match.group(3) or ""
        
        # If body is empty but subject has "and body", extract it
        if "and body" in subject.lower():
            parts = re.split(r'\s+and\s+body\s+', subject, flags=re.IGNORECASE)
            subject = parts[0]
            if len(parts) > 1 and not body:
                body = parts[1]
        elif "with body" in subject.lower():
            parts = re.split(r'\s+with\s+body\s+', subject, flags=re.IGNORECASE)
            subject = parts[0]
            if len(parts) > 1 and not body:
                body = parts[1]

        subject = subject.strip()
        body = body.strip()
        
        is_send = q_lower.startswith("send")
        
        return {
            "action": "send" if is_send else "draft",
            "to": to_email,
            "subject": subject or "Follow-up",
            "body": body or "Hello, just following up on our previous conversation."
        }

    # 2. Match Search intents
    # Matches: "find my latest email from customer@example.com"
    # Matches: "emails from test@example.com"
    for prefix in ["find my latest email from", "find emails from", "search emails from", "emails from", "from:"]:
        if q_lower.startswith(prefix):
            from_val = query_str[len(prefix):].strip()
            from_val = re.sub(r'[<>\'"]', '', from_val)
            return {
                "action": "search",
                "query": f"from:{from_val}"
            }
            
    # Matches: "find emails about pricing"
    # Matches: "search for pricing"
    for prefix in ["find emails about", "search emails about", "find emails containing", "search emails containing", "emails about", "search for"]:
        if q_lower.startswith(prefix):
            about_val = query_str[len(prefix):].strip()
            return {
                "action": "search",
                "query": about_val
            }
            
    # Default is simply running a raw query search
    return {
        "action": "search",
        "query": query_str
    }


@router.get("/query", response_model=dict)
async def query_emails(
    request: Request,
    q: str = Query(..., min_length=1, description="Natural language query"),
    db: Session = Depends(get_db),
    mail_service: MailService = Depends(get_mail_service),
):
    """
    Parse a natural language query (e.g. 'find my latest email from client@example.com' 
    or 'draft email to client@example.com with subject Quote') and run the corresponding action.
    """
    user_id = get_current_user_id(request)
    parsed = parse_natural_language_email_query(q)
    
    try:
        if parsed["action"] == "search":
            emails = await mail_service.search_messages(db, user_id, query=parsed["query"], limit=5, provider="gmail")
            return {
                "action": "search",
                "query": parsed["query"],
                "emails": [email.model_dump(by_alias=True) for email in emails]
            }
            
        elif parsed["action"] == "draft":
            res = await mail_service.create_draft(
                db,
                user_id=user_id,
                to=parsed["to"],
                cc=None,
                subject=parsed["subject"],
                body=parsed["body"],
                provider="gmail"
            )
            return {
                "action": "draft_created",
                "draft_id": res["draft_id"],
                "message": f"Successfully created email draft to {parsed['to']} with subject '{parsed['subject']}'!",
                "details": parsed
            }
            
        elif parsed["action"] == "send":
            res = await mail_service.send_message(
                db,
                user_id=user_id,
                to=parsed["to"],
                cc=None,
                subject=parsed["subject"],
                body=parsed["body"],
                provider="gmail",
                confirmation_required=True
            )
            return {
                "action": "confirmation_required",
                "draft_id": res.get("draft_id"),
                "message": res.get("message"),
                "details": parsed
            }
            
    except OAuthError as exc:
        raise _handle_oauth_error(exc) from exc

    raise HTTPException(status_code=400, detail="Unable to process natural language request")
