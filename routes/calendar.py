"""
Calendar-related HTTP routes.

Provides endpoints for listing, searching, and viewing Google Calendar events.
Requires user session authentication.
"""

import logging
from datetime import UTC, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from sqlalchemy.orm import Session

from db.database import get_db
from routes.auth import get_current_user_id
from schemas.auth_schema import ErrorResponse
from schemas.calendar_schema import CalendarEventResponse, CalendarEventCreate
from services.calendar_service import CalendarService, get_calendar_service
from services.oauth_service import OAuthError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _handle_oauth_error(exc: OAuthError) -> HTTPException:
    """Map OAuthError to appropriate HTTPException for calendar endpoints."""
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.error_type == "connection_missing":
        status_code = status.HTTP_400_BAD_REQUEST
    elif exc.error_type == "api_error":
        status_code = status.HTTP_502_BAD_GATEWAY
    elif exc.error_type == "token_refresh_failed":
        status_code = status.HTTP_401_UNAUTHORIZED

    return HTTPException(
        status_code=status_code,
        detail=ErrorResponse(
            error_type=exc.error_type,
            message=exc.message,
        ).model_dump(),
    )


@router.get(
    "/events",
    response_model=list[CalendarEventResponse],
    responses={401: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def list_calendar_events(
    request: Request,
    start_time: str | None = Query(None, description="ISO 8601 start time limit"),
    end_time: str | None = Query(None, description="ISO 8601 end time limit"),
    db: Session = Depends(get_db),
    calendar_service: CalendarService = Depends(get_calendar_service),
) -> list[CalendarEventResponse]:
    """
    Get the logged-in user's Google Calendar events in the given date range.
    Defaults to the current day (from now to 24 hours later) if no times are specified.
    """
    user_id = get_current_user_id(request)

    # Resolve date time parameters
    try:
        if start_time:
            parsed_start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        else:
            parsed_start = datetime.now(UTC)

        if end_time:
            parsed_end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        else:
            parsed_end = parsed_start + timedelta(days=1)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error_type="invalid_date_format",
                message="Start and end times must be in valid ISO 8601 format (e.g. YYYY-MM-DDTHH:MM:SSZ)",
            ).model_dump(),
        ) from exc

    try:
        events = await calendar_service.list_events(
            db,
            user_id=user_id,
            start_time=parsed_start,
            end_time=parsed_end,
        )
        return events
    except OAuthError as exc:
        raise _handle_oauth_error(exc) from exc


@router.get(
    "/events/{event_id}",
    response_model=CalendarEventResponse,
    responses={401: {"model": ErrorResponse}, 400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_calendar_event(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    calendar_service: CalendarService = Depends(get_calendar_service),
) -> CalendarEventResponse:
    """Get the full details of a specific calendar event from Google Calendar."""
    user_id = get_current_user_id(request)

    try:
        event = await calendar_service.get_event(db, user_id=user_id, event_id=event_id)
        return event
    except OAuthError as exc:
        raise _handle_oauth_error(exc) from exc


@router.get(
    "/search",
    response_model=list[CalendarEventResponse],
    responses={401: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def search_calendar_events(
    request: Request,
    query: str = Query(..., min_length=1, description="Search query string"),
    start_time: str | None = Query(None, description="ISO 8601 start time limit"),
    end_time: str | None = Query(None, description="ISO 8601 end time limit"),
    db: Session = Depends(get_db),
    calendar_service: CalendarService = Depends(get_calendar_service),
) -> list[CalendarEventResponse]:
    """Search Google Calendar events by query text (searches titles, descriptions, and attendees)."""
    user_id = get_current_user_id(request)

    # Parse optional date constraints
    parsed_start = None
    parsed_end = None
    try:
        if start_time:
            parsed_start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if end_time:
            parsed_end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error_type="invalid_date_format",
                message="Start and end times must be in valid ISO 8601 format (e.g. YYYY-MM-DDTHH:MM:SSZ)",
            ).model_dump(),
        ) from exc

    try:
        events = await calendar_service.search_events(
            db,
            user_id=user_id,
            query=query,
            start_time=parsed_start,
            end_time=parsed_end,
        )
        return events
    except OAuthError as exc:
        raise _handle_oauth_error(exc) from exc


import re

def parse_natural_language_query(query_str: str, base_time: datetime = None) -> tuple[datetime, datetime, str | None]:
    """
    Parse relative dates and keywords from a natural language query.
    Returns: (start_time, end_time, search_query)
    """
    if not base_time:
        base_time = datetime.now(UTC)
        
    q = query_str.lower().strip()
    
    # Initialize defaults
    start_time = base_time
    end_time = base_time + timedelta(days=1)
    search_query = None
    
    today_start = base_time.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Parse relative dates
    if "tomorrow" in q:
        start_time = today_start + timedelta(days=1)
        end_time = start_time + timedelta(days=1) - timedelta(seconds=1)
        q = q.replace("tomorrow", "")
    elif "today" in q:
        start_time = today_start
        end_time = today_start + timedelta(days=1) - timedelta(seconds=1)
        q = q.replace("today", "")
    elif "yesterday" in q:
        start_time = today_start - timedelta(days=1)
        end_time = today_start - timedelta(seconds=1)
        q = q.replace("yesterday", "")
    elif "next week" in q:
        days_to_monday = (0 - base_time.weekday() + 7) % 7
        if days_to_monday == 0:
            days_to_monday = 7
        start_time = today_start + timedelta(days=days_to_monday)
        end_time = start_time + timedelta(days=7) - timedelta(seconds=1)
        q = q.replace("next week", "")
    elif "this week" in q:
        days_to_monday = base_time.weekday()
        start_time = today_start - timedelta(days=days_to_monday)
        end_time = start_time + timedelta(days=7) - timedelta(seconds=1)
        q = q.replace("this week", "")
    else:
        weekdays = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        found_weekday = None
        is_next = False
        
        for day, idx in weekdays.items():
            if f"next {day}" in q:
                found_weekday = idx
                is_next = True
                q = q.replace(f"next {day}", "")
                break
            elif day in q:
                found_weekday = idx
                q = q.replace(day, "")
                break
                
        if found_weekday is not None:
            current_weekday = base_time.weekday()
            days_ahead = found_weekday - current_weekday
            if days_ahead <= 0:
                days_ahead += 7
            if is_next:
                days_ahead += 7
                
            start_time = today_start + timedelta(days=days_ahead)
            end_time = start_time + timedelta(days=1) - timedelta(seconds=1)

    # Extract keywords
    fillers = [
        "what", "are", "my", "events", "meetings", "on", "for", "do", 
        "i", "have", "any", "in", "at", "containing", "about", "show", 
        "list", "get", "fetch", "calendar", "schedule"
    ]
    
    words = re.findall(r'\b\w+\b', q)
    remaining_words = [w for w in words if w not in fillers]
    
    if remaining_words:
        search_query = " ".join(remaining_words)
        
    return start_time, end_time, search_query


@router.get("/query", response_model=dict)
async def query_calendar_events(
    request: Request,
    q: str = Query(..., min_length=1, description="Natural language query"),
    db: Session = Depends(get_db),
    calendar_service: CalendarService = Depends(get_calendar_service),
):
    """
    Parse a natural language query (e.g. "what are my events tomorrow")
    and return parsed parameters and matching Google Calendar events.
    """
    user_id = get_current_user_id(request)
    
    # Check if this is a creation query first
    creation_data = parse_creation_query(q, datetime.now(UTC))
    if creation_data:
        title, start_time, end_time, location, description = creation_data
        try:
            new_event = await calendar_service.create_event(
                db,
                user_id=user_id,
                title=title,
                start_time=start_time,
                end_time=end_time,
                location=location,
                description=description
            )
            return {
                "action": "created",
                "message": f"Successfully created event '{title}' on {start_time.strftime('%Y-%m-%d at %I:%M %p')}!",
                "events": [new_event.model_dump(mode="json")]
            }
        except OAuthError as exc:
            raise _handle_oauth_error(exc) from exc

    # Otherwise do a normal query
    start_time, end_time, search_query = parse_natural_language_query(q)
    try:
        if search_query:
            events = await calendar_service.search_events(
                db,
                user_id=user_id,
                query=search_query,
                start_time=start_time,
                end_time=end_time,
            )
        else:
            events = await calendar_service.list_events(
                db,
                user_id=user_id,
                start_time=start_time,
                end_time=end_time,
            )
            
        return {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "search_query": search_query,
            "events": [
                evt.model_dump(mode="json")
                for evt in events
            ]
        }
    except OAuthError as exc:
        raise _handle_oauth_error(exc) from exc


def parse_creation_query(query_str: str, base_time: datetime) -> tuple[str, datetime, datetime, str | None, str | None] | None:
    """
    Parse a query like: "create event [Title] tomorrow at 3pm" or "schedule [Title] next monday at 11:30"
    Returns: (title, start_time, end_time, location, description) or None if not a creation command.
    """
    q_lower = query_str.lower().strip()
    
    # Detect creation keywords at the start
    creation_prefixes = ["create", "add", "schedule", "new event", "put", "book"]
    is_creation = False
    prefix_matched = ""
    for prefix in creation_prefixes:
        if q_lower.startswith(prefix):
            is_creation = True
            prefix_matched = prefix
            break
            
    if not is_creation:
        return None
        
    content = query_str[len(prefix_matched):].strip()
    
    today_start = base_time.replace(hour=0, minute=0, second=0, microsecond=0)
    event_date = today_start
    
    # Check for relative dates
    if "tomorrow" in content.lower():
        event_date = today_start + timedelta(days=1)
        content = re.sub(r'(?i)\btomorrow\b', '', content)
    elif "today" in content.lower():
        event_date = today_start
        content = re.sub(r'(?i)\btoday\b', '', content)
    elif "next week" in content.lower():
        days_to_monday = (0 - base_time.weekday() + 7) % 7
        if days_to_monday == 0:
            days_to_monday = 7
        event_date = today_start + timedelta(days=days_to_monday)
        content = re.sub(r'(?i)\bnext week\b', '', content)
    else:
        weekdays = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        for day, idx in weekdays.items():
            if f"next {day}" in content.lower():
                current_weekday = base_time.weekday()
                days_ahead = idx - current_weekday
                if days_ahead <= 0:
                    days_ahead += 7
                days_ahead += 7
                event_date = today_start + timedelta(days=days_ahead)
                content = re.sub(r'(?i)\bnext ' + day + r'\b', '', content)
                break
            elif day in content.lower():
                current_weekday = base_time.weekday()
                days_ahead = idx - current_weekday
                if days_ahead <= 0:
                    days_ahead += 7
                event_date = today_start + timedelta(days=days_ahead)
                content = re.sub(r'(?i)\b' + day + r'\b', '', content)
                break
                
    # Extract time
    time_match = re.search(r'(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm|o\'clock)?', content, re.IGNORECASE)
    
    hour = 12
    minute = 0
    
    if time_match:
        hour_val = int(time_match.group(1))
        min_val = int(time_match.group(2)) if time_match.group(2) else 0
        ampm = time_match.group(3)
        
        if ampm:
            ampm = ampm.lower()
            if ampm == "pm" and hour_val < 12:
                hour_val += 12
            elif ampm == "am" and hour_val == 12:
                hour_val = 0
        elif hour_val < 8:
            hour_val += 12
            
        hour = hour_val
        minute = min_val
        content = content.replace(time_match.group(0), "")
        
    start_time = event_date.replace(hour=hour, minute=minute)
    end_time = start_time + timedelta(hours=1)
    
    # Clean up title
    title = content.strip()
    title = re.sub(r'^(?i)(?:called|named|event|meeting|task|for)\s+', '', title)
    title = re.sub(r'(?i)\s+(?:called|named|event|meeting|task|for)$', '', title)
    title = title.strip()
    
    if not title:
        title = "New Calendar Event"
        
    return title, start_time, end_time, None, "Created via AI Assistant"


@router.post("/events", response_model=CalendarEventResponse)
async def create_calendar_event(
    request: Request,
    event_data: CalendarEventCreate,
    db: Session = Depends(get_db),
    calendar_service: CalendarService = Depends(get_calendar_service),
):
    """Create a new Google Calendar event manually via form."""
    user_id = get_current_user_id(request)
    try:
        new_event = await calendar_service.create_event(
            db,
            user_id=user_id,
            title=event_data.title,
            start_time=event_data.start_time,
            end_time=event_data.end_time,
            location=event_data.location,
            description=event_data.description,
        )
        return new_event
    except OAuthError as exc:
        raise _handle_oauth_error(exc) from exc
