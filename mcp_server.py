"""
MCP Server exposing Google Calendar tools to AI agents.
Uses FastMCP from the 'mcp' library to define tools and run the server over stdio.
"""

from datetime import UTC, datetime
import json
import logging
import os
import sys

# Add the current directory to python path so we can import from db, models, services
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session
from db.database import SessionLocal
from services.calendar_service import get_calendar_service
from services.mail_service import get_mail_service
from services.crm_service import get_crm_service
from services.oauth_service import OAuthError

# Configure minimal logging to stderr (stdio transport requires stdout to be pure JSON-RPC)
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("mcp_calendar_server")

mcp = FastMCP("Google Workspace Mail & Calendar Server")
calendar_service = get_calendar_service()
mail_service = get_mail_service()
crm_service = get_crm_service()


def get_db_session() -> Session:
    """Helper to yield a database session for database operations."""
    return SessionLocal()


@mcp.tool()
async def list_events(
    start_time: str,
    end_time: str,
    user_id: int = 1
) -> str:
    """
    Fetch calendar events from Google Calendar between start_time and end_time.
    
    Args:
        start_time: ISO 8601 string (e.g., '2026-06-25T00:00:00Z')
        end_time: ISO 8601 string (e.g., '2026-06-26T00:00:00Z')
        user_id: The database ID of the user (defaults to 1)
    """
    logger.info("MCP Tool list_events called with start_time=%s, end_time=%s, user_id=%s", start_time, end_time, user_id)
    
    try:
        parsed_start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        parsed_end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    except ValueError as exc:
        return json.dumps({
            "status": "failed",
            "error_type": "invalid_date_format",
            "message": f"Start and end times must be in valid ISO 8601 format: {exc}"
        }, indent=2)

    db = get_db_session()
    try:
        events = await calendar_service.list_events(
            db,
            user_id=user_id,
            start_time=parsed_start,
            end_time=parsed_end
        )
        # Serialize list of Pydantic models
        return json.dumps([evt.model_dump(mode='json') for evt in events], indent=2)
    except OAuthError as exc:
        return json.dumps({
            "status": "failed",
            "error_type": exc.error_type,
            "message": exc.message
        }, indent=2)
    except Exception as exc:
        logger.exception("Unexpected error in list_events tool")
        return json.dumps({
            "status": "failed",
            "error_type": "internal_error",
            "message": str(exc)
        }, indent=2)
    finally:
        db.close()


@mcp.tool()
async def get_event(
    event_id: str,
    user_id: int = 1
) -> str:
    """
    Fetch full details of a specific calendar event from Google Calendar.
    
    Args:
        event_id: The unique identifier of the Google Calendar event
        user_id: The database ID of the user (defaults to 1)
    """
    logger.info("MCP Tool get_event called with event_id=%s, user_id=%s", event_id, user_id)
    
    db = get_db_session()
    try:
        event = await calendar_service.get_event(
            db,
            user_id=user_id,
            event_id=event_id
        )
        return json.dumps(event.model_dump(mode='json'), indent=2)
    except OAuthError as exc:
        return json.dumps({
            "status": "failed",
            "error_type": exc.error_type,
            "message": exc.message
        }, indent=2)
    except Exception as exc:
        logger.exception("Unexpected error in get_event tool")
        return json.dumps({
            "status": "failed",
            "error_type": "internal_error",
            "message": str(exc)
        }, indent=2)
    finally:
        db.close()


@mcp.tool()
async def search_events(
    query: str,
    start_time: str | None = None,
    end_time: str | None = None,
    user_id: int = 1
) -> str:
    """
    Search calendar events from Google Calendar by keyword in titles, descriptions, and attendees.
    
    Args:
        query: The search query term
        start_time: Optional ISO 8601 string to restrict search start window (e.g. '2026-06-25T00:00:00Z')
        end_time: Optional ISO 8601 string to restrict search end window (e.g. '2026-06-26T00:00:00Z')
        user_id: The database ID of the user (defaults to 1)
    """
    logger.info("MCP Tool search_events called with query=%s, user_id=%s", query, user_id)
    
    parsed_start = None
    parsed_end = None
    try:
        if start_time:
            parsed_start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if end_time:
            parsed_end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    except ValueError as exc:
        return json.dumps({
            "status": "failed",
            "error_type": "invalid_date_format",
            "message": f"Start and end times must be in valid ISO 8601 format: {exc}"
        }, indent=2)

    db = get_db_session()
    try:
        events = await calendar_service.search_events(
            db,
            user_id=user_id,
            query=query,
            start_time=parsed_start,
            end_time=parsed_end
        )
        return json.dumps([evt.model_dump(mode='json') for evt in events], indent=2)
    except OAuthError as exc:
        return json.dumps({
            "status": "failed",
            "error_type": exc.error_type,
            "message": exc.message
        }, indent=2)
    except Exception as exc:
        logger.exception("Unexpected error in search_events tool")
        return json.dumps({
            "status": "failed",
            "error_type": "internal_error",
            "message": str(exc)
        }, indent=2)
    finally:
        db.close()


@mcp.tool(name="mail.search_messages")
async def search_messages(
    query: str,
    limit: int = 10,
    provider: str = "gmail",
    user_id: int = 1
) -> str:
    """
    Search and retrieve emails matching the given query from Gmail.
    
    Args:
        query: Search keywords or filters (e.g., 'from:customer@example.com' or 'pricing')
        limit: Maximum number of messages to fetch (default: 10)
        provider: Mail provider to use (default: 'gmail')
        user_id: The database ID of the user (defaults to 1)
    """
    logger.info("MCP Tool search_messages called with query=%s, limit=%s, user_id=%s", query, limit, user_id)
    db = get_db_session()
    try:
        messages = await mail_service.search_messages(
            db,
            user_id=user_id,
            query=query,
            limit=limit,
            provider=provider
        )
        return json.dumps([msg.model_dump(by_alias=True) for msg in messages], indent=2)
    except OAuthError as exc:
        return json.dumps({
            "status": "failed",
            "error_type": exc.error_type,
            "message": exc.message
        }, indent=2)
    except Exception as exc:
        logger.exception("Unexpected error in search_messages tool")
        return json.dumps({
            "status": "failed",
            "error_type": "internal_error",
            "message": str(exc)
        }, indent=2)
    finally:
        db.close()


@mcp.tool(name="mail.read_message")
async def read_message(
    provider: str,
    message_id: str,
    user_id: int = 1
) -> str:
    """
    Read the full content (including subject, headers, and full body text) of an email.
    
    Args:
        provider: Mail provider to use ('gmail')
        message_id: The unique ID of the message to read
        user_id: The database ID of the user (defaults to 1)
    """
    logger.info("MCP Tool read_message called with message_id=%s, provider=%s, user_id=%s", message_id, provider, user_id)
    db = get_db_session()
    try:
        msg = await mail_service.read_message(
            db,
            user_id=user_id,
            message_id=message_id,
            provider=provider
        )
        return json.dumps(msg.model_dump(by_alias=True), indent=2)
    except OAuthError as exc:
        return json.dumps({
            "status": "failed",
            "error_type": exc.error_type,
            "message": exc.message
        }, indent=2)
    except Exception as exc:
        logger.exception("Unexpected error in read_message tool")
        return json.dumps({
            "status": "failed",
            "error_type": "internal_error",
            "message": str(exc)
        }, indent=2)
    finally:
        db.close()


@mcp.tool(name="mail.create_draft")
async def create_draft(
    to: str,
    cc: str | None = None,
    subject: str = "",
    body: str = "",
    provider: str = "gmail",
    user_id: int = 1
) -> str:
    """
    Create an email draft in Gmail. Can be done directly without safety blocks.
    
    Args:
        to: Recipient email address
        cc: Optional Carbon Copy email address(es) (comma-separated)
        subject: Subject line of the email
        body: Body text content of the email
        provider: Mail provider to use (default: 'gmail')
        user_id: The database ID of the user (defaults to 1)
    """
    logger.info("MCP Tool create_draft called to=%s, subject=%s, user_id=%s", to, subject, user_id)
    db = get_db_session()
    try:
        res = await mail_service.create_draft(
            db,
            user_id=user_id,
            to=to,
            cc=cc,
            subject=subject,
            body=body,
            provider=provider
        )
        return json.dumps(res, indent=2)
    except OAuthError as exc:
        return json.dumps({
            "status": "failed",
            "error_type": exc.error_type,
            "message": exc.message
        }, indent=2)
    except Exception as exc:
        logger.exception("Unexpected error in create_draft tool")
        return json.dumps({
            "status": "failed",
            "error_type": "internal_error",
            "message": str(exc)
        }, indent=2)
    finally:
        db.close()


@mcp.tool(name="mail.send_message")
async def send_message(
    to: str,
    cc: str | None = None,
    subject: str = "",
    body: str = "",
    provider: str = "gmail",
    confirmation_required: bool = True,
    user_id: int = 1
) -> str:
    """
    Send an email. Requires recipient whitelisting. By default, creates a draft first for user confirmation.
    
    Args:
        to: Recipient email address
        cc: Optional Carbon Copy email address(es) (comma-separated)
        subject: Subject line of the email
        body: Body text content of the email
        provider: Mail provider to use (default: 'gmail')
        confirmation_required: Set to True (default) to require user confirmation. If False, sends immediately (only allowed for whitelisted addresses).
        user_id: The database ID of the user (defaults to 1)
    """
    logger.info("MCP Tool send_message called to=%s, confirmation_required=%s, user_id=%s", to, confirmation_required, user_id)
    db = get_db_session()
    try:
        res = await mail_service.send_message(
            db,
            user_id=user_id,
            to=to,
            cc=cc,
            subject=subject,
            body=body,
            provider=provider,
            confirmation_required=confirmation_required
        )
        return json.dumps(res, indent=2)
    except OAuthError as exc:
        return json.dumps({
            "status": "failed",
            "error_type": exc.error_type,
            "message": exc.message
        }, indent=2)
    except Exception as exc:
        logger.exception("Unexpected error in send_message tool")
        return json.dumps({
            "status": "failed",
            "error_type": "internal_error",
            "message": str(exc)
        }, indent=2)
    finally:
        db.close()


@mcp.tool(name="mail.reply_to_message")
async def reply_to_message(
    provider: str,
    message_id: str,
    body: str,
    user_id: int = 1
) -> str:
    """
    Reply to an existing email message. Creates a reply draft in Gmail.
    
    Args:
        provider: Mail provider to use ('gmail')
        message_id: The ID of the original email message to reply to
        body: The reply body text content
        user_id: The database ID of the user (defaults to 1)
    """
    logger.info("MCP Tool reply_to_message called for message_id=%s, user_id=%s", message_id, user_id)
    db = get_db_session()
    try:
        res = await mail_service.reply_to_message(
            db,
            user_id=user_id,
            message_id=message_id,
            body=body,
            provider=provider
        )
        return json.dumps(res, indent=2)
    except OAuthError as exc:
        return json.dumps({
            "status": "failed",
            "error_type": exc.error_type,
            "message": exc.message
        }, indent=2)
    except Exception as exc:
        logger.exception("Unexpected error in reply_to_message tool")
        return json.dumps({
            "status": "failed",
            "error_type": "internal_error",
            "message": str(exc)
        }, indent=2)
    finally:
        db.close()


# --- CRM Tools ---

@mcp.tool(name="crm.search_contacts")
async def search_contacts(
    query: str,
    provider: str | None = None,
    user_id: int = 1
) -> str:
    """
    Search contacts across connected CRM platforms.
    
    Args:
        query: Name, email, or details to search for
        provider: Optional CRM provider ('hubspot', 'salesforce', or 'zoho')
        user_id: The database ID of the user (defaults to 1)
    """
    logger.info("MCP Tool search_contacts called query=%s, provider=%s, user_id=%s", query, provider, user_id)
    db = get_db_session()
    try:
        res = await crm_service.search_contacts(db, user_id=user_id, query=query, provider=provider)
        return json.dumps(res, indent=2)
    except Exception as exc:
        logger.exception("Error in search_contacts tool")
        return json.dumps({"status": "failed", "error": str(exc)}, indent=2)
    finally:
        db.close()


@mcp.tool(name="crm.get_contact")
async def get_contact(
    provider: str,
    contact_id: str,
    user_id: int = 1
) -> str:
    """
    Fetch full contact details including notes and tasks from a connected CRM.
    
    Args:
        provider: The CRM provider ('hubspot', 'salesforce', or 'zoho')
        contact_id: The unique CRM identifier of the contact
        user_id: The database ID of the user (defaults to 1)
    """
    logger.info("MCP Tool get_contact called provider=%s, contact_id=%s, user_id=%s", provider, contact_id, user_id)
    db = get_db_session()
    try:
        res = await crm_service.get_contact(db, user_id=user_id, provider=provider, contact_id=contact_id)
        return json.dumps(res, indent=2)
    except Exception as exc:
        logger.exception("Error in get_contact tool")
        return json.dumps({"status": "failed", "error": str(exc)}, indent=2)
    finally:
        db.close()


@mcp.tool(name="crm.search_accounts")
async def search_accounts(
    query: str,
    provider: str | None = None,
    user_id: int = 1
) -> str:
    """
    Search accounts/companies across connected CRM platforms.
    
    Args:
        query: Company name or domain to search for
        provider: Optional CRM provider ('hubspot', 'salesforce', or 'zoho')
        user_id: The database ID of the user (defaults to 1)
    """
    logger.info("MCP Tool search_accounts called query=%s, provider=%s, user_id=%s", query, provider, user_id)
    db = get_db_session()
    try:
        res = await crm_service.search_accounts(db, user_id=user_id, query=query, provider=provider)
        return json.dumps(res, indent=2)
    except Exception as exc:
        logger.exception("Error in search_accounts tool")
        return json.dumps({"status": "failed", "error": str(exc)}, indent=2)
    finally:
        db.close()


@mcp.tool(name="crm.search_deals")
async def search_deals(
    query: str,
    provider: str | None = None,
    user_id: int = 1
) -> str:
    """
    Search deals/opportunities across connected CRM platforms.
    
    Args:
        query: Deal name or stage to search for
        provider: Optional CRM provider ('hubspot', 'salesforce', or 'zoho')
        user_id: The database ID of the user (defaults to 1)
    """
    logger.info("MCP Tool search_deals called query=%s, provider=%s, user_id=%s", query, provider, user_id)
    db = get_db_session()
    try:
        res = await crm_service.search_deals(db, user_id=user_id, query=query, provider=provider)
        return json.dumps(res, indent=2)
    except Exception as exc:
        logger.exception("Error in search_deals tool")
        return json.dumps({"status": "failed", "error": str(exc)}, indent=2)
    finally:
        db.close()


@mcp.tool(name="crm.create_note")
async def create_note(
    provider: str,
    entity_type: str,
    entity_id: str,
    note_text: str,
    user_id: int = 1
) -> str:
    """
    Add a note to a contact, account, or deal.
    
    Args:
        provider: The CRM provider ('hubspot', 'salesforce', or 'zoho')
        entity_type: The object type ('contact', 'account', or 'deal')
        entity_id: The unique CRM identifier of the entity
        note_text: The content of the note
        user_id: The database ID of the user (defaults to 1)
    """
    logger.info("MCP Tool create_note called provider=%s, entity=%s, user_id=%s", provider, entity_type, user_id)
    db = get_db_session()
    try:
        res = await crm_service.create_note(
            db, user_id=user_id, provider=provider, entity_type=entity_type, entity_id=entity_id, note_text=note_text
        )
        return json.dumps(res, indent=2)
    except Exception as exc:
        logger.exception("Error in create_note tool")
        return json.dumps({"status": "failed", "error": str(exc)}, indent=2)
    finally:
        db.close()


@mcp.tool(name="crm.create_task")
async def create_task(
    provider: str,
    entity_type: str,
    entity_id: str,
    task_title: str,
    due_date: str | None = None,
    owner: str | None = None,
    user_id: int = 1
) -> str:
    """
    Create a follow-up task on a contact, account, or deal.
    
    Args:
        provider: The CRM provider ('hubspot', 'salesforce', or 'zoho')
        entity_type: The object type ('contact', 'account', or 'deal')
        entity_id: The unique CRM identifier of the entity
        task_title: The title/description of the task
        due_date: Optional ISO 8601 string for due date (e.g., '2026-07-15T12:00:00Z')
        owner: Optional name of the task owner/assignee
        user_id: The database ID of the user (defaults to 1)
    """
    logger.info("MCP Tool create_task called provider=%s, entity=%s, title=%s, user_id=%s", provider, entity_type, task_title, user_id)
    db = get_db_session()
    try:
        res = await crm_service.create_task(
            db, user_id=user_id, provider=provider, entity_type=entity_type, entity_id=entity_id,
            task_title=task_title, due_date=due_date, owner=owner
        )
        return json.dumps(res, indent=2)
    except Exception as exc:
        logger.exception("Error in create_task tool")
        return json.dumps({"status": "failed", "error": str(exc)}, indent=2)
    finally:
        db.close()


@mcp.tool(name="crm.propose_deal_update")
async def propose_deal_update(
    provider: str,
    deal_id: str,
    proposed_changes: str,  # Pass proposed changes as a JSON string to allow flexible properties
    reason: str | None = None,
    user_id: int = 1
) -> str:
    """
    Propose a deal update (e.g. stage, amount) without directly editing CRM. Returns a pending proposal.
    
    Args:
        provider: The CRM provider ('hubspot', 'salesforce', or 'zoho')
        deal_id: The unique CRM identifier of the deal
        proposed_changes: JSON string representing changes, e.g. '{"stage": "Negotiation", "amount": 90000}'
        reason: The rationale/reason for the proposal
        user_id: The database ID of the user (defaults to 1)
    """
    logger.info("MCP Tool propose_deal_update called provider=%s, deal_id=%s, user_id=%s", provider, deal_id, user_id)
    db = get_db_session()
    try:
        changes = json.loads(proposed_changes)
        res = await crm_service.propose_deal_update(
            db, user_id=user_id, provider=provider, deal_id=deal_id, proposed_changes=changes, reason=reason
        )
        return json.dumps(res, indent=2)
    except Exception as exc:
        logger.exception("Error in propose_deal_update tool")
        return json.dumps({"status": "failed", "error": str(exc)}, indent=2)
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run()
