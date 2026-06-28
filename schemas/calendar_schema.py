"""Pydantic schemas for normalized calendar event response bodies."""

from datetime import datetime
from pydantic import BaseModel, Field


class OrganizerInfo(BaseModel):
    name: str | None = None
    email: str | None = None


class AttendeeInfo(BaseModel):
    name: str | None = None
    email: str | None = None
    status: str | None = None  # e.g., 'accepted', 'declined', 'tentative', 'needsAction'


class CalendarEventResponse(BaseModel):
    provider: str = Field(default="google")
    event_id: str
    title: str
    description: str | None = None
    start_time: datetime | str
    end_time: datetime | str
    organizer: OrganizerInfo | None = None
    attendees: list[AttendeeInfo] = Field(default_factory=list)
    meeting_link: str | None = None
    location: str | None = None
    status: str | None = None  # e.g., 'confirmed', 'tentative', 'cancelled'


class CalendarEventCreate(BaseModel):
    title: str = Field(..., min_length=1)
    start_time: datetime
    end_time: datetime
    location: str | None = None
    description: str | None = None
