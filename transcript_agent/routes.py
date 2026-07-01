"""API routes for the Sales Transcript HubSpot Agent POC."""

import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import httpx

from db.database import get_db
from routes.auth import get_current_user_id
from services.oauth_service import OAuthError
from transcript_agent.schemas import TranscriptAgentRunRequest, TranscriptAgentApplyRequest
from transcript_agent.service import TranscriptAgentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hubspot-transcript-agent", tags=["transcript-agent"])
agent_service = TranscriptAgentService()


@router.post("/run")
async def run_transcript_agent(
    request: Request,
    body: TranscriptAgentRunRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Analyze call transcript, fetch CRM state, and propose updates."""
    user_id = get_current_user_id(request)
    try:
        return await agent_service.run_transcript_agent(
            db, user_id, body.provider, body.deal_id, body.transcript
        )
    except OAuthError as exc:
        raise HTTPException(status_code=400, detail={"error_type": exc.error_type, "message": exc.message})
    except httpx.HTTPStatusError as exc:
        try:
            err_data = exc.response.json()
            err_msg = err_data.get("message") or str(exc)
        except Exception:
            err_msg = str(exc)
        raise HTTPException(status_code=400, detail={"error_type": "validation_error", "message": err_msg})
    except httpx.RequestError as exc:
        logger.warning("Transcript agent run network error: %s", exc)
        raise HTTPException(status_code=503, detail={"error_type": "network_error", "message": "Network connection to CRM timed out. Please try again."})
    except Exception as exc:
        logger.exception("Transcript agent analysis failed")
        raise HTTPException(status_code=500, detail={"error_type": "internal_error", "message": str(exc)})


@router.post("/apply")
async def apply_transcript_changes(
    request: Request,
    body: TranscriptAgentApplyRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Apply approved transcript updates via HubSpot MCP tools."""
    user_id = get_current_user_id(request)
    try:
        return await agent_service.apply_transcript_changes(
            db, user_id, body.provider, body.approved_changes
        )
    except OAuthError as exc:
        raise HTTPException(status_code=400, detail={"error_type": exc.error_type, "message": exc.message})
    except httpx.HTTPStatusError as exc:
        try:
            err_data = exc.response.json()
            err_msg = err_data.get("message") or str(exc)
        except Exception:
            err_msg = str(exc)
        raise HTTPException(status_code=400, detail={"error_type": "validation_error", "message": err_msg})
    except httpx.RequestError as exc:
        logger.warning("Transcript agent apply network error: %s", exc)
        raise HTTPException(status_code=503, detail={"error_type": "network_error", "message": "Network connection to CRM timed out. Please try again."})
    except Exception as exc:
        logger.exception("Applying approved updates failed")
        raise HTTPException(status_code=500, detail={"error_type": "internal_error", "message": str(exc)})
