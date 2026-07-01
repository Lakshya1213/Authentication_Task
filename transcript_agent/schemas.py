"""Pydantic schemas for the B2B Sales Transcript Agent POC."""

from pydantic import BaseModel
from typing import Any

class TranscriptAgentRunRequest(BaseModel):
    deal_id: str
    transcript: str
    provider: str = "hubspot"

class TranscriptAgentApplyRequest(BaseModel):
    approved_changes: list[dict]
    provider: str = "hubspot"
