"""
Google Calendar connector service.

Handles fetching, searching, and normalizing calendar events from Google API.
Ensures token validity by refreshing if necessary before making API requests.
"""

import logging
from datetime import UTC, datetime, timedelta
import httpx
from sqlalchemy.orm import Session

from models.audit_log import AuditLog
from models.connected_account import ConnectedAccount
from schemas.calendar_schema import CalendarEventResponse, OrganizerInfo, AttendeeInfo
from services.oauth_service import get_oauth_service, OAuthError
from utils.encryption import decrypt_token

logger = logging.getLogger(__name__)


class CalendarService:
    def __init__(self) -> None:
        self.oauth_service = get_oauth_service()

    async def _get_valid_google_token(self, db: Session, user_id: int) -> str:
        """
        Retrieve and decrypt the user's Google access token.
        Automatically triggers a token refresh if expired or close to expiring.
        """
        account = (
            db.query(ConnectedAccount)
            .filter(
                ConnectedAccount.user_id == user_id,
                ConnectedAccount.provider == "google",
            )
            .one_or_none()
        )

        if not account:
            raise OAuthError("Google account is not connected", error_type="connection_missing")

        if account.status != "connected":
            raise OAuthError(
                f"Google account connection status is {account.status}. Please reconnect.",
                error_type="invalid_connection",
            )

        token = account.oauth_token
        if not token:
            raise OAuthError("No active credentials found for Google", error_type="missing_token")

        # Refresh if token expires in less than 60 seconds or is already expired
        now_utc = datetime.now(UTC)
        is_expired = token.expires_at is None or token.expires_at <= now_utc + timedelta(seconds=60)

        if is_expired:
            logger.info("Google access token is expired or close to expiring. Refreshing...")
            try:
                await self.oauth_service.refresh_access_token(db, user_id=user_id, provider="google")
                # Refresh session object
                db.refresh(token)
            except Exception as exc:
                logger.exception("Failed to refresh Google token automatically")
                # Mark connection as failed/expired
                account.status = "expired"
                db.commit()
                raise OAuthError("Unable to refresh Google access token", error_type="token_refresh_failed") from exc

        try:
            return decrypt_token(token.encrypted_access_token)
        except Exception as exc:
            logger.exception("Token decryption failed")
            raise OAuthError("Failed to decrypt access token", error_type="encryption_error") from exc

    def _normalize_google_event(self, event: dict) -> CalendarEventResponse:
        """Map raw Google Calendar event payload to normalized CalendarEventResponse."""
        start_data = event.get("start", {})
        start_time = start_data.get("dateTime") or start_data.get("date")

        end_data = event.get("end", {})
        end_time = end_data.get("dateTime") or end_data.get("date")

        organizer_data = event.get("organizer", {})
        organizer = OrganizerInfo(
            name=organizer_data.get("displayName") or organizer_data.get("email"),
            email=organizer_data.get("email"),
        ) if organizer_data else None

        attendees = []
        for att in event.get("attendees", []):
            attendees.append(
                AttendeeInfo(
                    name=att.get("displayName") or att.get("email"),
                    email=att.get("email"),
                    status=att.get("responseStatus"),
                )
            )

        # Get meeting link (Google Meet is in hangoutLink)
        meeting_link = event.get("hangoutLink")

        return CalendarEventResponse(
            provider="google",
            event_id=event.get("id"),
            title=event.get("summary", "(No Title)"),
            description=event.get("description"),
            start_time=start_time,
            end_time=end_time,
            organizer=organizer,
            attendees=attendees,
            meeting_link=meeting_link,
            location=event.get("location"),
            status=event.get("status"),
        )

    def _log_audit(self, db: Session, user_id: int, action: str, status: str) -> None:
        """Create a calendar audit log entry."""
        try:
            log = AuditLog(
                user_id=user_id,
                action=action,
                provider="google",
                status=status,
            )
            db.add(log)
            db.commit()
        except Exception:
            logger.exception("Failed to write calendar audit log")

    async def list_events(
        self,
        db: Session,
        user_id: int,
        start_time: datetime,
        end_time: datetime,
        query: str | None = None,
    ) -> list[CalendarEventResponse]:
        """Fetch Google Calendar events between start_time and end_time, applying optional search filters."""
        access_token = await self._get_valid_google_token(db, user_id)

        # Format times as ISO 8601 strings
        time_min = start_time.isoformat()
        time_max = end_time.isoformat()

        params = {
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        if query:
            params["q"] = query

        url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

        async with httpx.AsyncClient() as client:
            try:
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(url, headers=headers, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                logger.exception("Google Calendar list events API call failed")
                self._log_audit(db, user_id, "list_events", "failed")
                raise OAuthError("Failed to fetch events from Google Calendar", error_type="api_error") from exc

        events = data.get("items", [])
        normalized_events = [self._normalize_google_event(evt) for evt in events]

        self._log_audit(db, user_id, "list_events", "success")
        return normalized_events

    async def get_event(self, db: Session, user_id: int, event_id: str) -> CalendarEventResponse:
        """Fetch detailed information for a single Google Calendar event."""
        access_token = await self._get_valid_google_token(db, user_id)

        url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{event_id}"

        async with httpx.AsyncClient() as client:
            try:
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(url, headers=headers, timeout=10.0)
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                logger.exception("Google Calendar get event API call failed for event_id=%s", event_id)
                self._log_audit(db, user_id, f"get_event:{event_id}", "failed")
                raise OAuthError(f"Failed to retrieve event {event_id} from Google Calendar", error_type="api_error") from exc

        normalized = self._normalize_google_event(data)
        self._log_audit(db, user_id, f"get_event:{event_id}", "success")
        return normalized

    async def search_events(
        self,
        db: Session,
        user_id: int,
        query: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[CalendarEventResponse]:
        """
        Search user events for matching query.
        Defaults to a search window of 30 days in the past to 90 days in the future if times are omitted.
        """
        if not start_time:
            start_time = datetime.now(UTC) - timedelta(days=30)
        if not end_time:
            end_time = datetime.now(UTC) + timedelta(days=90)

        # Google's list events API supports `q` parameter which queries summary, description, location, attendee name/email, etc.
        events = await self.list_events(db, user_id, start_time, end_time, query=query)
        self._log_audit(db, user_id, f"search_events:{query}", "success")
        return events


    async def create_event(
        self,
        db: Session,
        user_id: int,
        title: str,
        start_time: datetime,
        end_time: datetime,
        location: str | None = None,
        description: str | None = None,
    ) -> CalendarEventResponse:
        """Create a new event in Google Calendar."""
        access_token = await self._get_valid_google_token(db, user_id)

        url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
        
        body = {
            "summary": title,
            "location": location,
            "description": description,
            "start": {
                "dateTime": start_time.isoformat(),
            },
            "end": {
                "dateTime": end_time.isoformat(),
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                }
                response = await client.post(url, headers=headers, json=body, timeout=10.0)
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                logger.exception("Google Calendar create event API call failed")
                self._log_audit(db, user_id, "create_event", "failed")
                raise OAuthError("Failed to create event in Google Calendar", error_type="api_error") from exc

        normalized = self._normalize_google_event(data)
        self._log_audit(db, user_id, "create_event", "success")
        return normalized


def get_calendar_service() -> CalendarService:
    """FastAPI dependency for the Google Calendar service."""
    return CalendarService()
