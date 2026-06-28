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
from services.oauth_service import OAuthError

# Configure minimal logging to stderr (stdio transport requires stdout to be pure JSON-RPC)
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("mcp_calendar_server")

mcp = FastMCP("Google Calendar Server")
calendar_service = get_calendar_service()


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


if __name__ == "__main__":
    mcp.run()
