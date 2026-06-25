"""Pydantic schemas for auth API request/response bodies."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    status: str = "failed"
    error_type: str
    message: str


class ConnectedAppResponse(BaseModel):
    provider: str
    status: str
    scopes: str | None = None
    connected_at: datetime | None = None


class OAuthSuccessResponse(BaseModel):
    status: str = "success"
    message: str
    user: "UserSummary"


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    picture: str | None = None


class DisconnectResponse(BaseModel):
    status: str = "success"
    message: str
    provider: str = Field(default="google")


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    provider: str | None
    status: str
    created_at: datetime
