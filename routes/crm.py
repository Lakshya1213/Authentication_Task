"""CRM Integration HTTP routes."""

import logging
import httpx
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from models.deal_proposal import DealProposal
from routes.auth import get_current_user_id
from services.crm_service import CRMService, get_crm_service
from services.oauth_service import OAuthError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crm", tags=["crm"])


# --- Request/Response Schemas ---

class CreateNoteRequest(BaseModel):
    provider: str
    entity_type: str
    entity_id: str
    note_text: str


class CreateTaskRequest(BaseModel):
    provider: str
    entity_type: str
    entity_id: str
    task_title: str
    due_date: str | None = None
    owner: str | None = None


class CreateContactRequest(BaseModel):
    provider: str
    first_name: str
    last_name: str
    email: str
    phone: str | None = None


class CreateCompanyRequest(BaseModel):
    provider: str
    name: str
    industry: str | None = None
    website: str | None = None


class CreateDealRequest(BaseModel):
    provider: str
    name: str
    stage: str
    amount: float


class ProposeDealUpdateRequest(BaseModel):
    provider: str
    deal_id: str
    proposed_changes: dict
    reason: str | None = None


# --- Route Implementations ---

@router.get("/search")
async def search_crm(
    request: Request,
    query: str = "",
    provider: str | None = None,
    object_type: str | None = None,  # contact, account, deal
    db: Session = Depends(get_db),
    crm_service: CRMService = Depends(get_crm_service),
) -> dict[str, list[Any]]:
    """Search CRM contacts, accounts, and deals across connected providers."""
    user_id = get_current_user_id(request)
    
    contacts = []
    accounts = []
    deals = []

    try:
        # Resolve search scopes
        if not object_type or object_type == "contact":
            contacts = await crm_service.search_contacts(db, user_id, query, provider)
        if not object_type or object_type == "account":
            accounts = await crm_service.search_accounts(db, user_id, query, provider)
        if not object_type or object_type == "deal":
            deals = await crm_service.search_deals(db, user_id, query, provider)
            
        return {
            "contacts": contacts,
            "accounts": accounts,
            "deals": deals
        }
    except OAuthError as exc:
        raise HTTPException(status_code=400, detail={"error_type": exc.error_type, "message": exc.message})
    except httpx.RequestError as exc:
        logger.warning("CRM search network error: %s", exc)
        raise HTTPException(status_code=503, detail={"error_type": "network_error", "message": "Network connection to CRM provider timed out. Please try again."})
    except Exception as exc:
        logger.exception("CRM search failed")
        raise HTTPException(status_code=500, detail={"error_type": "internal_error", "message": str(exc)})


@router.get("/detail")
async def get_crm_detail(
    request: Request,
    provider: str,
    object_type: str,
    object_id: str,
    db: Session = Depends(get_db),
    crm_service: CRMService = Depends(get_crm_service),
) -> Any:
    """Fetch detail for a specific CRM entity."""
    user_id = get_current_user_id(request)
    
    try:
        if object_type == "contact":
            return await crm_service.get_contact(db, user_id, provider, object_id)
        elif object_type == "account":
            return await crm_service.get_account(db, user_id, provider, object_id)
        elif object_type == "deal":
            return await crm_service.get_deal(db, user_id, provider, object_id)
        else:
            raise HTTPException(status_code=400, detail="Invalid object_type")
    except OAuthError as exc:
        raise HTTPException(status_code=400 if exc.error_type != "not_found" else 404, detail={"error_type": exc.error_type, "message": exc.message})
    except httpx.RequestError as exc:
        logger.warning("CRM detail fetch network error: %s", exc)
        raise HTTPException(status_code=503, detail={"error_type": "network_error", "message": "Network connection to CRM provider timed out. Please try again."})
    except Exception as exc:
        logger.exception("CRM fetch details failed")
        raise HTTPException(status_code=500, detail={"error_type": "internal_error", "message": str(exc)})


@router.post("/write/note")
async def create_note(
    request: Request,
    body: CreateNoteRequest,
    db: Session = Depends(get_db),
    crm_service: CRMService = Depends(get_crm_service),
) -> Any:
    """Add a note to a contact, account, or deal."""
    user_id = get_current_user_id(request)
    try:
        return await crm_service.create_note(
            db, user_id, body.provider, body.entity_type, body.entity_id, body.note_text
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
        logger.warning("CRM note create network error: %s", exc)
        raise HTTPException(status_code=503, detail={"error_type": "network_error", "message": "Network connection to CRM provider timed out. Please try again."})
    except Exception as exc:
        logger.exception("Create note failed")
        raise HTTPException(status_code=500, detail={"error_type": "internal_error", "message": str(exc)})


@router.post("/write/task")
async def create_task(
    request: Request,
    body: CreateTaskRequest,
    db: Session = Depends(get_db),
    crm_service: CRMService = Depends(get_crm_service),
) -> Any:
    """Create a task associated with a contact, account, or deal."""
    user_id = get_current_user_id(request)
    try:
        return await crm_service.create_task(
            db, user_id, body.provider, body.entity_type, body.entity_id, body.task_title, body.due_date, body.owner
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
        logger.warning("CRM task create network error: %s", exc)
        raise HTTPException(status_code=503, detail={"error_type": "network_error", "message": "Network connection to CRM provider timed out. Please try again."})
    except Exception as exc:
        logger.exception("Create task failed")
        raise HTTPException(status_code=500, detail={"error_type": "internal_error", "message": str(exc)})


@router.post("/write/contact")
async def create_contact(
    request: Request,
    body: CreateContactRequest,
    db: Session = Depends(get_db),
    crm_service: CRMService = Depends(get_crm_service),
) -> Any:
    """Create a contact directly in the CRM."""
    user_id = get_current_user_id(request)
    try:
        return await crm_service.create_contact(
            db, user_id, body.provider, body.first_name, body.last_name, body.email, body.phone
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
        logger.warning("CRM contact create network error: %s", exc)
        raise HTTPException(status_code=503, detail={"error_type": "network_error", "message": "Network connection to CRM provider timed out. Please try again."})
    except Exception as exc:
        logger.exception("Create contact failed")
        raise HTTPException(status_code=500, detail={"error_type": "internal_error", "message": str(exc)})


@router.post("/write/company")
async def create_company(
    request: Request,
    body: CreateCompanyRequest,
    db: Session = Depends(get_db),
    crm_service: CRMService = Depends(get_crm_service),
) -> Any:
    """Create a company/account directly in the CRM."""
    user_id = get_current_user_id(request)
    try:
        return await crm_service.create_company(
            db, user_id, body.provider, body.name, body.industry, body.website
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
        logger.warning("CRM company create network error: %s", exc)
        raise HTTPException(status_code=503, detail={"error_type": "network_error", "message": "Network connection to CRM provider timed out. Please try again."})
    except Exception as exc:
        logger.exception("Create company failed")
        raise HTTPException(status_code=500, detail={"error_type": "internal_error", "message": str(exc)})


@router.post("/write/deal")
async def create_deal(
    request: Request,
    body: CreateDealRequest,
    db: Session = Depends(get_db),
    crm_service: CRMService = Depends(get_crm_service),
) -> Any:
    """Create a deal directly in the CRM."""
    user_id = get_current_user_id(request)
    try:
        return await crm_service.create_deal(
            db, user_id, body.provider, body.name, body.stage, body.amount
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
        logger.warning("CRM deal create network error: %s", exc)
        raise HTTPException(status_code=503, detail={"error_type": "network_error", "message": "Network connection to CRM provider timed out. Please try again."})
    except Exception as exc:
        logger.exception("Create deal failed")
        raise HTTPException(status_code=500, detail={"error_type": "internal_error", "message": str(exc)})


@router.post("/propose-deal-update")
async def propose_deal_update(
    request: Request,
    body: ProposeDealUpdateRequest,
    db: Session = Depends(get_db),
    crm_service: CRMService = Depends(get_crm_service),
) -> Any:
    """Propose an update to a deal's stage or details."""
    user_id = get_current_user_id(request)
    try:
        return await crm_service.propose_deal_update(
            db, user_id, body.provider, body.deal_id, body.proposed_changes, body.reason
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
        logger.warning("CRM deal update proposal network error: %s", exc)
        raise HTTPException(status_code=503, detail={"error_type": "network_error", "message": "Network connection to CRM provider timed out. Please try again."})
    except Exception as exc:
        logger.exception("Propose deal update failed")
        raise HTTPException(status_code=500, detail={"error_type": "internal_error", "message": str(exc)})


@router.get("/proposals")
def list_proposals(
    request: Request,
    db: Session = Depends(get_db),
) -> list[Any]:
    """List deal update proposals for the authenticated user."""
    user_id = get_current_user_id(request)
    proposals = (
        db.query(DealProposal)
        .filter(DealProposal.user_id == user_id)
        .order_by(DealProposal.created_at.desc())
        .all()
    )
    # Serialize proposals list
    return [
        {
            "id": p.id,
            "provider": p.provider,
            "deal_id": p.deal_id,
            "proposed_changes": p.proposed_changes,
            "reason": p.reason,
            "status": p.status,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat() if p.updated_at else None
        }
        for p in proposals
    ]


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    crm_service: CRMService = Depends(get_crm_service),
) -> Any:
    """Approve and apply a pending deal update proposal."""
    user_id = get_current_user_id(request)
    try:
        return await crm_service.execute_deal_update(db, user_id, proposal_id)
    except OAuthError as exc:
        raise HTTPException(status_code=400 if exc.error_type != "not_found" else 404, detail={"error_type": exc.error_type, "message": exc.message})
    except Exception as exc:
        logger.exception("Approve proposal failed")
        raise HTTPException(status_code=500, detail={"error_type": "internal_error", "message": str(exc)})


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(
    proposal_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Reject a pending deal update proposal."""
    user_id = get_current_user_id(request)
    proposal = db.query(DealProposal).filter(DealProposal.id == proposal_id, DealProposal.user_id == user_id).one_or_none()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
        
    if proposal.status != "pending":
         return {"status": "error", "message": f"Proposal already {proposal.status}"}
         
    proposal.status = "rejected"
    db.commit()
    return {"status": "success", "message": "Proposal rejected"}
