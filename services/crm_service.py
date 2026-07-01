"""CRM Service — routing and data normalization across CRM providers."""

from datetime import UTC, datetime, timedelta
import logging
import httpx
from sqlalchemy.orm import Session

from models.audit_log import AuditLog
from models.connected_account import ConnectedAccount
from models.deal_proposal import DealProposal
from services.oauth_service import get_oauth_service, OAuthError
from services.sandbox_crm import SandboxCRMService
from utils.encryption import decrypt_token

logger = logging.getLogger(__name__)


class CRMService:
    def __init__(self) -> None:
        self.sandbox = SandboxCRMService()
        self.oauth_service = get_oauth_service()

    async def _get_valid_token(self, db: Session, user_id: int, provider: str) -> str:
        """Fetch, refresh if necessary, and decrypt the provider OAuth token."""
        provider_key = provider.lower()
        account = (
            db.query(ConnectedAccount)
            .filter(
                ConnectedAccount.user_id == user_id,
                ConnectedAccount.provider == provider_key,
            )
            .one_or_none()
        )

        if not account:
            raise OAuthError(f"{provider.capitalize()} account is not connected", error_type="connection_missing")

        if account.status != "connected":
            raise OAuthError(
                f"{provider.capitalize()} account connection status is {account.status}. Please reconnect.",
                error_type="invalid_connection",
            )

        token = account.oauth_token
        if not token:
            raise OAuthError(f"No active credentials found for {provider}", error_type="missing_token")

        # Refresh if token expires in less than 60 seconds or is already expired
        now_utc = datetime.now(UTC)
        is_expired = token.expires_at is None or token.expires_at <= now_utc + timedelta(seconds=60)

        if is_expired:
            logger.info("CRM access token for %s is expired or close to expiring. Refreshing...", provider)
            try:
                await self.oauth_service.refresh_access_token(db, user_id=user_id, provider=provider_key)
                db.refresh(token)
            except Exception as exc:
                logger.exception("Failed to refresh token automatically")
                account.status = "expired"
                db.commit()
                raise OAuthError(f"Unable to refresh {provider} access token", error_type="token_refresh_failed") from exc

        try:
            return decrypt_token(token.encrypted_access_token)
        except Exception as exc:
            logger.exception("Token decryption failed")
            raise OAuthError("Failed to decrypt access token", error_type="encryption_error") from exc

    def _log_audit(self, db: Session, user_id: int, action: str, provider: str, status: str) -> None:
        """Create a CRM audit log entry."""
        try:
            log = AuditLog(
                user_id=user_id,
                action=action,
                provider=provider.lower(),
                status=status,
            )
            db.add(log)
            db.commit()
        except Exception:
            logger.exception("Failed to write CRM audit log")

    def _get_connected_providers(self, db: Session, user_id: int) -> list[str]:
        """Get list of active CRM provider connections for a user."""
        accounts = (
            db.query(ConnectedAccount)
            .filter(
                ConnectedAccount.user_id == user_id,
                ConnectedAccount.status == "connected",
                ConnectedAccount.provider.in_(["hubspot", "zoho", "salesforce"])
            )
            .all()
        )
        return [acc.provider for acc in accounts]

    # --- Read Operations ---

    async def search_contacts(self, db: Session, user_id: int, query: str, provider: str | None = None) -> list[dict]:
        """Search contacts across one or all connected CRM systems."""
        providers = [provider] if provider else self._get_connected_providers(db, user_id)
        if not providers:
            raise OAuthError("No CRM providers connected. Please connect HubSpot, Salesforce, or Zoho first.", error_type="connection_missing")

        results = []
        for p in providers:
            p_key = p.lower()
            try:
                token = await self._get_valid_token(db, user_id, p_key)
                if token.startswith("mock_access_token"):
                    res = self.sandbox.search_contacts(db, user_id, query, p_key)
                    results.extend(res)
                else:
                    # Real API Call (HubSpot Example)
                    if p_key == "hubspot":
                        res = await self._search_hubspot_contacts(token, query)
                        results.extend(res)
                    else:
                        # Salesforce and Zoho placeholders
                        results.extend(self.sandbox.search_contacts(db, user_id, query, p_key))
                
                self._log_audit(db, user_id, "crm_search_contacts", p_key, "success")
            except Exception as exc:
                logger.error("Search contacts failed for provider %s: %s", p_key, exc)
                self._log_audit(db, user_id, "crm_search_contacts", p_key, "failed")
                if provider: # If user requested a specific provider, propagate the error
                    raise

        return results

    async def get_contact(self, db: Session, user_id: int, provider: str, contact_id: str) -> dict:
        """Fetch detailed contact information by ID."""
        p_key = provider.lower()
        try:
            token = await self._get_valid_token(db, user_id, p_key)
            if token.startswith("mock_access_token"):
                res = self.sandbox.get_contact(db, user_id, p_key, contact_id)
            else:
                if p_key == "hubspot":
                    res = await self._get_hubspot_contact(token, contact_id)
                else:
                    res = self.sandbox.get_contact(db, user_id, p_key, contact_id)
            
            if not res:
                raise OAuthError("Contact not found", error_type="not_found")
                
            self._log_audit(db, user_id, "crm_get_contact", p_key, "success")
            return res
        except Exception as exc:
            logger.error("Get contact failed for %s: %s", p_key, exc)
            self._log_audit(db, user_id, "crm_get_contact", p_key, "failed")
            raise

    async def search_accounts(self, db: Session, user_id: int, query: str, provider: str | None = None) -> list[dict]:
        """Search accounts/companies across connected CRMs."""
        providers = [provider] if provider else self._get_connected_providers(db, user_id)
        if not providers:
            raise OAuthError("No CRM providers connected. Please connect HubSpot, Salesforce, or Zoho first.", error_type="connection_missing")

        results = []
        for p in providers:
            p_key = p.lower()
            try:
                token = await self._get_valid_token(db, user_id, p_key)
                if token.startswith("mock_access_token"):
                    res = self.sandbox.search_accounts(db, user_id, query, p_key)
                    results.extend(res)
                else:
                    if p_key == "hubspot":
                        res = await self._search_hubspot_companies(token, query)
                        results.extend(res)
                    else:
                        results.extend(self.sandbox.search_accounts(db, user_id, query, p_key))
                
                self._log_audit(db, user_id, "crm_search_accounts", p_key, "success")
            except Exception as exc:
                logger.error("Search accounts failed for provider %s: %s", p_key, exc)
                self._log_audit(db, user_id, "crm_search_accounts", p_key, "failed")
                if provider:
                    raise

        return results

    async def get_account(self, db: Session, user_id: int, provider: str, account_id: str) -> dict:
        """Fetch detailed account/company information by ID."""
        p_key = provider.lower()
        try:
            token = await self._get_valid_token(db, user_id, p_key)
            if token.startswith("mock_access_token"):
                res = self.sandbox.get_account(db, user_id, p_key, account_id)
            else:
                if p_key == "hubspot":
                    res = await self._get_hubspot_company(token, account_id)
                else:
                    res = self.sandbox.get_account(db, user_id, p_key, account_id)
            
            if not res:
                raise OAuthError("Account not found", error_type="not_found")
                
            self._log_audit(db, user_id, "crm_get_account", p_key, "success")
            return res
        except Exception as exc:
            logger.error("Get account failed for %s: %s", p_key, exc)
            self._log_audit(db, user_id, "crm_get_account", p_key, "failed")
            raise

    async def search_deals(self, db: Session, user_id: int, query: str, provider: str | None = None) -> list[dict]:
        """Search deals/opportunities across connected CRMs."""
        providers = [provider] if provider else self._get_connected_providers(db, user_id)
        if not providers:
            raise OAuthError("No CRM providers connected. Please connect HubSpot, Salesforce, or Zoho first.", error_type="connection_missing")

        results = []
        for p in providers:
            p_key = p.lower()
            try:
                token = await self._get_valid_token(db, user_id, p_key)
                if token.startswith("mock_access_token"):
                    res = self.sandbox.search_deals(db, user_id, query, p_key)
                    results.extend(res)
                else:
                    if p_key == "hubspot":
                        res = await self._search_hubspot_deals(token, query)
                        results.extend(res)
                    else:
                        results.extend(self.sandbox.search_deals(db, user_id, query, p_key))
                
                self._log_audit(db, user_id, "crm_search_deals", p_key, "success")
            except Exception as exc:
                logger.error("Search deals failed for provider %s: %s", p_key, exc)
                self._log_audit(db, user_id, "crm_search_deals", p_key, "failed")
                if provider:
                    raise

        return results

    async def get_deal(self, db: Session, user_id: int, provider: str, deal_id: str) -> dict:
        """Fetch detailed deal information by ID."""
        p_key = provider.lower()
        try:
            token = await self._get_valid_token(db, user_id, p_key)
            if token.startswith("mock_access_token"):
                res = self.sandbox.get_deal(db, user_id, p_key, deal_id)
            else:
                if p_key == "hubspot":
                    res = await self._get_hubspot_deal(token, deal_id)
                else:
                    res = self.sandbox.get_deal(db, user_id, p_key, deal_id)
            
            if not res:
                raise OAuthError("Deal not found", error_type="not_found")
                
            self._log_audit(db, user_id, "crm_get_deal", p_key, "success")
            return res
        except Exception as exc:
            logger.error("Get deal failed for %s: %s", p_key, exc)
            self._log_audit(db, user_id, "crm_get_deal", p_key, "failed")
            raise

    # --- Write Operations ---

    async def create_note(self, db: Session, user_id: int, provider: str, entity_type: str, entity_id: str, note_text: str) -> dict:
        """Create a note on a contact, account, or deal."""
        p_key = provider.lower()
        try:
            token = await self._get_valid_token(db, user_id, p_key)
            if token.startswith("mock_access_token"):
                res = self.sandbox.create_note(db, user_id, p_key, entity_type, entity_id, note_text)
            else:
                if p_key == "hubspot":
                    res = await self._create_hubspot_note(token, entity_type, entity_id, note_text)
                else:
                    res = self.sandbox.create_note(db, user_id, p_key, entity_type, entity_id, note_text)
            
            self._log_audit(db, user_id, "crm_create_note", p_key, "success")
            return res
        except Exception as exc:
            logger.error("Create note failed: %s", exc)
            self._log_audit(db, user_id, "crm_create_note", p_key, "failed")
            raise

    async def create_task(self, db: Session, user_id: int, provider: str, entity_type: str, entity_id: str, task_title: str, due_date: str | None = None, owner: str | None = None) -> dict:
        """Create a follow-up task on a contact, account, or deal."""
        p_key = provider.lower()
        try:
            token = await self._get_valid_token(db, user_id, p_key)
            if token.startswith("mock_access_token"):
                res = self.sandbox.create_task(db, user_id, p_key, entity_type, entity_id, task_title, due_date, owner)
            else:
                if p_key == "hubspot":
                    res = await self._create_hubspot_task(token, entity_type, entity_id, task_title, due_date, owner)
                else:
                    res = self.sandbox.create_task(db, user_id, p_key, entity_type, entity_id, task_title, due_date, owner)
            
            self._log_audit(db, user_id, "crm_create_task", p_key, "success")
            return res
        except Exception as exc:
            logger.error("Create task failed: %s", exc)
            self._log_audit(db, user_id, "crm_create_task", p_key, "failed")
            raise

    async def create_contact(self, db: Session, user_id: int, provider: str, first_name: str, last_name: str, email: str, phone: str | None = None) -> dict:
        """Create a contact directly in the CRM."""
        p_key = provider.lower()
        try:
            token = await self._get_valid_token(db, user_id, p_key)
            if token.startswith("mock_access_token"):
                res = self.sandbox.create_contact(db, user_id, p_key, first_name, last_name, email, phone)
            else:
                if p_key == "hubspot":
                    res = await self._create_hubspot_contact(token, first_name, last_name, email, phone)
                else:
                    res = self.sandbox.create_contact(db, user_id, p_key, first_name, last_name, email, phone)
            
            self._log_audit(db, user_id, "crm_create_contact", p_key, "success")
            return res
        except Exception as exc:
            logger.error("Create contact failed: %s", exc)
            self._log_audit(db, user_id, "crm_create_contact", p_key, "failed")
            raise

    async def create_company(self, db: Session, user_id: int, provider: str, name: str, industry: str | None = None, website: str | None = None) -> dict:
        """Create a company/account directly in the CRM."""
        p_key = provider.lower()
        try:
            token = await self._get_valid_token(db, user_id, p_key)
            if token.startswith("mock_access_token"):
                res = self.sandbox.create_account(db, user_id, p_key, name, industry, website)
            else:
                if p_key == "hubspot":
                    res = await self._create_hubspot_company(token, name, industry, website)
                else:
                    res = self.sandbox.create_account(db, user_id, p_key, name, industry, website)
            
            self._log_audit(db, user_id, "crm_create_company", p_key, "success")
            return res
        except Exception as exc:
            logger.error("Create company failed: %s", exc)
            self._log_audit(db, user_id, "crm_create_company", p_key, "failed")
            raise

    async def create_deal(self, db: Session, user_id: int, provider: str, name: str, stage: str, amount: float) -> dict:
        """Create a deal directly in the CRM."""
        p_key = provider.lower()
        try:
            token = await self._get_valid_token(db, user_id, p_key)
            if token.startswith("mock_access_token"):
                res = self.sandbox.create_deal(db, user_id, p_key, name, stage, amount)
            else:
                if p_key == "hubspot":
                    res = await self._create_hubspot_deal(token, name, stage, amount)
                else:
                    res = self.sandbox.create_deal(db, user_id, p_key, name, stage, amount)
            
            self._log_audit(db, user_id, "crm_create_deal", p_key, "success")
            return res
        except Exception as exc:
            logger.error("Create deal failed: %s", exc)
            self._log_audit(db, user_id, "crm_create_deal", p_key, "failed")
            raise

    async def propose_deal_update(self, db: Session, user_id: int, provider: str, deal_id: str, proposed_changes: dict, reason: str | None = None) -> dict:
        """Propose a deal change (requires approval). Saves to proposals table."""
        p_key = provider.lower()
        try:
            # Check connection first
            await self._get_valid_token(db, user_id, p_key)
            
            # Create a pending deal proposal record
            proposal = DealProposal(
                user_id=user_id,
                provider=p_key,
                deal_id=deal_id,
                proposed_changes=proposed_changes,
                reason=reason,
                status="pending"
            )
            db.add(proposal)
            db.commit()
            db.refresh(proposal)
            
            self._log_audit(db, user_id, "crm_propose_deal_update", p_key, "success")
            return {
                "status": "proposal_created",
                "proposal_id": proposal.id,
                "deal_id": deal_id,
                "proposed_changes": proposed_changes,
                "message": "Deal update proposed successfully. Approval is required before execution."
            }
        except Exception as exc:
            logger.error("Propose deal update failed: %s", exc)
            self._log_audit(db, user_id, "crm_propose_deal_update", p_key, "failed")
            raise

    async def execute_deal_update(self, db: Session, user_id: int, proposal_id: int) -> dict:
        """Apply an approved deal proposal to the target CRM."""
        proposal = db.query(DealProposal).filter(DealProposal.id == proposal_id, DealProposal.user_id == user_id).one_or_none()
        if not proposal:
            raise OAuthError("Proposal not found", error_type="not_found")
            
        if proposal.status != "pending":
            return {"status": "error", "message": f"Proposal already {proposal.status}"}

        p_key = proposal.provider
        try:
            token = await self._get_valid_token(db, user_id, p_key)
            if token.startswith("mock_access_token"):
                res = self.sandbox.update_deal(db, user_id, p_key, proposal.deal_id, proposal.proposed_changes)
            else:
                if p_key == "hubspot":
                    res = await self._update_hubspot_deal(token, proposal.deal_id, proposal.proposed_changes)
                else:
                    res = self.sandbox.update_deal(db, user_id, p_key, proposal.deal_id, proposal.proposed_changes)
            
            if res.get("status") == "success":
                proposal.status = "approved"
                db.commit()
                self._log_audit(db, user_id, "crm_execute_deal_update", p_key, "success")
                return {"status": "success", "message": "Deal updated in CRM", "crm_response": res}
            else:
                raise Exception(res.get("message", "CRM write failed"))
                
        except Exception as exc:
            logger.error("Execute approved deal update failed: %s", exc)
            self._log_audit(db, user_id, "crm_execute_deal_update", p_key, "failed")
            raise

    # --- Real HubSpot API Integration ---

    async def _search_hubspot_contacts(self, token: str, query: str) -> list[dict]:
        """Search contacts in HubSpot CRM."""
        url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        # HubSpot search payload
        payload = {
            "limit": 20,
            "properties": ["firstname", "lastname", "email", "phone", "hubspot_owner_id"]
        }
        if query:
            payload["filterGroups"] = [
                {
                    "filters": [{
                        "propertyName": "firstname",
                        "operator": "CONTAINS_TOKEN",
                        "value": query
                    }]
                },
                {
                    "filters": [{
                        "propertyName": "lastname",
                        "operator": "CONTAINS_TOKEN",
                        "value": query
                    }]
                },
                {
                    "filters": [{
                        "propertyName": "email",
                        "operator": "CONTAINS_TOKEN",
                        "value": query
                    }]
                }
            ]
            
        async with httpx.AsyncClient() as client:
            r = await client.post(url, headers=headers, json=payload, timeout=10.0)
            if r.status_code == 400 and query:
                # Fallback to fetching all contacts and filtering in memory if HubSpot search operator is picky
                r = await client.get("https://api.hubapi.com/crm/v3/objects/contacts?properties=firstname,lastname,email,phone,hubspot_owner_id", headers=headers, timeout=10.0)
                r.raise_for_status()
                data = r.json()
                results = data.get("results", [])
                filtered = []
                for x in results:
                    props = x.get("properties", {})
                    fn = props.get("firstname") or ""
                    ln = props.get("lastname") or ""
                    em = props.get("email") or ""
                    if query.lower() in fn.lower() or query.lower() in ln.lower() or query.lower() in em.lower():
                        filtered.append(x)
                return [self._normalize_hubspot_contact(c) for c in filtered]
                
            r.raise_for_status()
            data = r.json()
            return [self._normalize_hubspot_contact(c) for c in data.get("results", [])]

    async def _get_hubspot_contact(self, token: str, contact_id: str) -> dict:
        url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}?properties=firstname,lastname,email,phone,hubspot_owner_id"
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=headers, timeout=10.0)
            r.raise_for_status()
            contact = r.json()
            
            # Fetch engagements/notes associated with this contact if available
            notes = []
            tasks = []
            try:
                # Associated notes lookup (HubSpot engagements API)
                assoc_url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}/associations/notes"
                assoc_r = await client.get(assoc_url, headers=headers, timeout=5.0)
                if assoc_r.status_code == 200:
                    note_ids = [x["id"] for x in assoc_r.json().get("results", [])]
                    for nid in note_ids[:5]:
                        n_url = f"https://api.hubapi.com/crm/v3/objects/notes/{nid}?properties=hs_note_body,createdate"
                        n_r = await client.get(n_url, headers=headers, timeout=5.0)
                        if n_r.status_code == 200:
                            nd = n_r.json()
                            notes.append({
                                "id": nd["id"],
                                "text": nd.get("properties", {}).get("hs_note_body") or "",
                                "created_at": nd.get("properties", {}).get("createdate") or ""
                            })
                            
                # Associated tasks lookup
                t_assoc_url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}/associations/tasks"
                t_assoc_r = await client.get(t_assoc_url, headers=headers, timeout=5.0)
                if t_assoc_r.status_code == 200:
                    task_ids = [x["id"] for x in t_assoc_r.json().get("results", [])]
                    for tid in task_ids[:5]:
                        t_url = f"https://api.hubapi.com/crm/v3/objects/tasks/{tid}?properties=hs_task_subject,hs_task_status,hs_task_remind_date"
                        t_r = await client.get(t_url, headers=headers, timeout=5.0)
                        if t_r.status_code == 200:
                            td = t_r.json()
                            tasks.append({
                                "id": td["id"],
                                "title": td.get("properties", {}).get("hs_task_subject") or "",
                                "due_date": td.get("properties", {}).get("hs_task_remind_date") or "",
                                "owner": "Sales Rep"
                            })
            except Exception as e:
                logger.warning("Error fetching HubSpot engagements: %s", e)

            res = self._normalize_hubspot_contact(contact)
            res["notes"] = notes
            res["tasks"] = tasks
            return res

    async def _search_hubspot_companies(self, token: str, query: str) -> list[dict]:
        url = "https://api.hubapi.com/crm/v3/objects/companies/search"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "limit": 20,
            "properties": ["name", "industry", "domain"]
        }
        if query:
            payload["filterGroups"] = [{
                "filters": [{
                    "propertyName": "name",
                    "operator": "CONTAINS_TOKEN",
                    "value": query
                }]
            }]
        async with httpx.AsyncClient() as client:
            r = await client.post(url, headers=headers, json=payload, timeout=10.0)
            if r.status_code == 400 and query:
                r = await client.get("https://api.hubapi.com/crm/v3/objects/companies?properties=name,industry,domain", headers=headers, timeout=10.0)
                r.raise_for_status()
                data = r.json()
                results = [x for x in data.get("results", []) if query.lower() in (x.get("properties", {}).get("name") or "").lower()]
                return [self._normalize_hubspot_company(c) for c in results]
                
            r.raise_for_status()
            data = r.json()
            return [self._normalize_hubspot_company(c) for c in data.get("results", [])]

    async def _get_hubspot_company(self, token: str, company_id: str) -> dict:
        url = f"https://api.hubapi.com/crm/v3/objects/companies/{company_id}?properties=name,industry,domain"
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=headers, timeout=10.0)
            r.raise_for_status()
            company = r.json()
            return self._normalize_hubspot_company(company)

    async def _search_hubspot_deals(self, token: str, query: str) -> list[dict]:
        url = "https://api.hubapi.com/crm/v3/objects/deals/search"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "limit": 20,
            "properties": ["dealname", "dealstage", "amount", "closedate"]
        }
        if query:
            payload["filterGroups"] = [{
                "filters": [{
                    "propertyName": "dealname",
                    "operator": "CONTAINS_TOKEN",
                    "value": query
                }]
            }]
        async with httpx.AsyncClient() as client:
            r = await client.post(url, headers=headers, json=payload, timeout=10.0)
            if r.status_code == 400 and query:
                r = await client.get("https://api.hubapi.com/crm/v3/objects/deals?properties=dealname,dealstage,amount,closedate", headers=headers, timeout=10.0)
                r.raise_for_status()
                data = r.json()
                results = [x for x in data.get("results", []) if query.lower() in (x.get("properties", {}).get("dealname") or "").lower()]
                return [self._normalize_hubspot_deal(c) for c in results]
                
            r.raise_for_status()
            data = r.json()
            return [self._normalize_hubspot_deal(c) for c in data.get("results", [])]

    async def _get_hubspot_deal(self, token: str, deal_id: str) -> dict:
        url = f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}?properties=dealname,dealstage,amount,closedate"
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=headers, timeout=10.0)
            r.raise_for_status()
            deal = r.json()
            return self._normalize_hubspot_deal(deal)

    async def _create_hubspot_note(self, token: str, entity_type: str, entity_id: str, note_text: str) -> dict:
        url = "https://api.hubapi.com/crm/v3/objects/notes"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        import datetime
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"
        
        payload = {
            "properties": {
                "hs_note_body": note_text,
                "hs_timestamp": now_iso
            }
        }
        
        # Determine association type name
        assoc_type = ""
        if entity_type.lower() == "contact":
            assoc_type = "contact_to_note"
        elif entity_type.lower() == "account":
            assoc_type = "company_to_note"
        elif entity_type.lower() == "deal":
            assoc_type = "deal_to_note"
            
        if assoc_type:
            payload["associations"] = [{
                "to": {"id": entity_id},
                "types": [{
                    "associationCategory": "HUBSPOT_DEFINED",
                    "associationTypeId": self._get_hubspot_assoc_type_id(assoc_type)
                }]
            }]

        async with httpx.AsyncClient() as client:
            r = await client.post(url, headers=headers, json=payload, timeout=10.0)
            if not r.is_success:
                logger.error("HubSpot note creation failed: Status %s, Response: %s", r.status_code, r.text)
            r.raise_for_status()
            res = r.json()
            return {
                "status": "success",
                "message": "note_created",
                "note_id": res["id"],
                "entity_type": entity_type,
                "entity_id": entity_id
            }

    async def _create_hubspot_task(self, token: str, entity_type: str, entity_id: str, task_title: str, due_date: str | None = None, owner: str | None = None) -> dict:
        url = "https://api.hubapi.com/crm/v3/objects/tasks"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Convert date to millisecond timestamp for HubSpot properties
        import datetime as dt_module
        task_time = due_date
        if not due_date:
            task_time = dt_module.datetime.utcnow().isoformat() + "Z"
                
        payload = {
            "properties": {
                "hs_task_subject": task_title,
                "hs_task_status": "NOT_STARTED",
                "hs_timestamp": task_time
            }
        }

        assoc_type = ""
        if entity_type.lower() == "contact":
            assoc_type = "contact_to_task"
        elif entity_type.lower() == "account":
            assoc_type = "company_to_task"
        elif entity_type.lower() == "deal":
            assoc_type = "deal_to_task"

        if assoc_type:
            payload["associations"] = [{
                "to": {"id": entity_id},
                "types": [{
                    "associationCategory": "HUBSPOT_DEFINED",
                    "associationTypeId": self._get_hubspot_assoc_type_id(assoc_type)
                }]
            }]

        async with httpx.AsyncClient() as client:
            r = await client.post(url, headers=headers, json=payload, timeout=10.0)
            if not r.is_success:
                logger.error("HubSpot task creation failed: Status %s, Response: %s", r.status_code, r.text)
            r.raise_for_status()
            res = r.json()
            return {
                "status": "success",
                "message": "task_created",
                "task_id": res["id"],
                "entity_type": entity_type,
                "entity_id": entity_id
            }

    async def _update_hubspot_deal(self, token: str, deal_id: str, proposed_changes: dict) -> dict:
        url = f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Map proposed changes to HubSpot deal properties
        props = {}
        if "stage" in proposed_changes:
            props["dealstage"] = self._map_deal_stage_to_hubspot(proposed_changes["stage"])
        if "amount" in proposed_changes:
            props["amount"] = str(proposed_changes["amount"])
        if "name" in proposed_changes:
            props["dealname"] = proposed_changes["name"]
            
        payload = {"properties": props}
        async with httpx.AsyncClient() as client:
            r = await client.patch(url, headers=headers, json=payload, timeout=10.0)
            r.raise_for_status()
            res = r.json()
            return {
                "status": "success",
                "message": "deal_updated",
                "deal": self._normalize_hubspot_deal(res)
            }

    def _map_deal_stage_to_hubspot(self, stage: str) -> str:
        mapping = {
            "proposal sent": "contractsent",
            "negotiation": "decisionmakerboughtin",
            "needs analysis": "appointmentscheduled",
            "closed won": "closedwon",
            "closed lost": "closedlost"
        }
        return mapping.get(stage.lower(), stage.lower().replace(" ", ""))

    async def _create_hubspot_contact(self, token: str, first_name: str, last_name: str, email: str, phone: str | None = None) -> dict:
        url = "https://api.hubapi.com/crm/v3/objects/contacts"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "properties": {
                "firstname": first_name,
                "lastname": last_name,
                "email": email
            }
        }
        if phone:
            payload["properties"]["phone"] = phone
            
        async with httpx.AsyncClient() as client:
            r = await client.post(url, headers=headers, json=payload, timeout=10.0)
            if not r.is_success:
                logger.error("HubSpot contact creation failed: Status %s, Response: %s", r.status_code, r.text)
            r.raise_for_status()
            res = r.json()
            return self._normalize_hubspot_contact(res)

    def _map_company_industry_to_hubspot(self, industry: str) -> str | None:
        if not industry:
            return None
        allowed = [
            "ACCOUNTING", "AIRLINES_AVIATION", "ALTERNATIVE_DISPUTE_RESOLUTION", "ALTERNATIVE_MEDICINE", "ANIMATION",
            "APPAREL_FASHION", "ARCHITECTURE_PLANNING", "ARTS_AND_CRAFTS", "AUTOMOTIVE", "AVIATION_AEROSPACE",
            "BANKING", "BIOTECHNOLOGY", "BROADCAST_MEDIA", "BUILDING_MATERIALS", "BUSINESS_SUPPLIES_AND_EQUIPMENT",
            "CAPITAL_MARKETS", "CHEMICALS", "CIVIC_SOCIAL_ORGANIZATION", "CIVIL_ENGINEERING", "COMMERCIAL_REAL_ESTATE",
            "COMPUTER_NETWORK_SECURITY", "COMPUTER_GAMES", "COMPUTER_HARDWARE", "COMPUTER_NETWORKING", "COMPUTER_SOFTWARE",
            "INTERNET", "CONSTRUCTION", "CONSUMER_ELECTRONICS", "CONSUMER_GOODS", "CONSUMER_SERVICES", "COSMETICS", "DAIRY",
            "DEFENSE_SPACE", "DESIGN", "EDUCATION_MANAGEMENT", "E_LEARNING", "ELECTRICAL_ELECTRONIC_MANUFACTURING",
            "ENTERTAINMENT", "ENVIRONMENTAL_SERVICES", "EVENTS_SERVICES", "EXECUTIVE_OFFICE", "FACILITIES_SERVICES",
            "FARMING", "FINANCIAL_SERVICES", "FINE_ART", "FISHERY", "FOOD_BEVERAGES", "FOOD_PRODUCTION", "FUND_RAISING",
            "FURNITURE", "GAMBLING_CASINOS", "GLASS_CERAMICS_CONCRETE", "GOVERNMENT_ADMINISTRATION", "GOVERNMENT_RELATIONS",
            "GRAPHIC_DESIGN", "HEALTH_WELLNESS_AND_FITNESS", "HIGHER_EDUCATION", "HOSPITAL_HEALTH_CARE", "HOSPITALITY",
            "HUMAN_RESOURCES", "IMPORT_AND_EXPORT", "INDIVIDUAL_FAMILY_SERVICES", "INDUSTRIAL_AUTOMATION",
            "INFORMATION_SERVICES", "INFORMATION_TECHNOLOGY_AND_SERVICES", "INSURANCE", "INTERNATIONAL_AFFAIRS",
            "INTERNATIONAL_TRADE_AND_DEVELOPMENT", "INVESTMENT_BANKING", "INVESTMENT_MANAGEMENT", "JUDICIARY",
            "LAW_ENFORCEMENT", "LAW_PRACTICE", "LEGAL_SERVICES", "LEGISLATIVE_OFFICE", "LEISURE_TRAVEL_TOURISM",
            "LIBRARIES", "LOGISTICS_AND_SUPPLY_CHAIN", "LUXURY_GOODS_JEWELRY", "MACHINERY", "MANAGEMENT_CONSULTING",
            "MARITIME", "MARKET_RESEARCH", "MARKETING_AND_ADVERTISING", "MECHANICAL_OR_INDUSTRIAL_ENGINEERING",
            "MEDIA_PRODUCTION", "MEDICAL_DEVICES", "MEDICAL_PRACTICE", "MENTAL_HEALTH_CARE", "MILITARY", "MINING_METALS",
            "MOTION_PICTURES_AND_FILM", "MUSEUMS_AND_INSTITUTIONS", "MUSIC", "NANOTECHNOLOGY", "NEWSPAPERS",
            "NON_PROFIT_ORGANIZATION_MANAGEMENT", "OIL_ENERGY", "ONLINE_MEDIA", "OUTSOURCING_OFFSHORING",
            "PACKAGE_FREIGHT_DELIVERY", "PACKAGING_AND_CONTAINERS", "PAPER_FOREST_PRODUCTS", "PERFORMING_ARTS",
            "PHARMACEUTICALS", "PHILANTHROPY", "PHOTOGRAPHY", "PLASTICS", "POLITICAL_ORGANIZATION",
            "PRIMARY_SECONDARY_EDUCATION", "PRINTING", "PROFESSIONAL_TRAINING_COACHING", "PROGRAM_DEVELOPMENT",
            "PUBLIC_POLICY", "PUBLIC_RELATIONS_AND_COMMUNICATIONS", "PUBLIC_SAFETY", "PUBLISHING", "RAILROAD_MANUFACTURE",
            "RANCHING", "REAL_ESTATE", "RECREATIONAL_FACILITIES_AND_SERVICES", "RELIGIOUS_INSTITUTIONS",
            "RENEWABLES_ENVIRONMENT", "RESEARCH", "RESTAURANTS", "RETAIL", "SECURITY_AND_INVESTIGATIONS",
            "SEMICONDUCTORS", "SHIPBUILDING", "SPORTING_GOODS", "SPORTS", "STAFFING_AND_RECRUITING", "SUPERMARKETS",
            "TELECOMMUNICATIONS", "TEXTILES", "THINK_TANKS", "TOBACCO", "TRANSLATION_AND_LOCALIZATION",
            "TRANSPORTATION_TRUCKING_RAILROAD", "UTILITIES", "VENTURE_CAPITAL_PRIVATE_EQUITY", "VETERINARY",
            "WAREHOUSING", "WHOLESALE", "WINE_AND_SPIRITS", "WIRELESS", "WRITING_AND_EDITING", "MOBILE_GAMES"
        ]
        
        normalized = industry.strip().upper().replace(" ", "_").replace("&", "AND").replace("-", "_")
        if normalized in allowed:
            return normalized
            
        for opt in allowed:
            if normalized in opt or opt in normalized:
                return opt
                
        synonyms = {
            "AI": "COMPUTER_SOFTWARE",
            "ARTIFICIAL_INTELLIGENCE": "COMPUTER_SOFTWARE",
            "TECH": "INFORMATION_TECHNOLOGY_AND_SERVICES",
            "SOFTWARE": "COMPUTER_SOFTWARE",
            "SAAS": "COMPUTER_SOFTWARE",
            "FINTECH": "FINANCIAL_SERVICES"
        }
        if normalized in synonyms:
            return synonyms[normalized]
            
        return None

    async def _create_hubspot_company(self, token: str, name: str, industry: str | None = None, website: str | None = None) -> dict:
        url = "https://api.hubapi.com/crm/v3/objects/companies"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "properties": {
                "name": name
            }
        }
        if industry:
            mapped_ind = self._map_company_industry_to_hubspot(industry)
            if mapped_ind:
                payload["properties"]["industry"] = mapped_ind
        if website:
            # HubSpot "domain" expects a clean domain name (e.g., "stark.com") and will throw a 400 Bad Request
            # validation error if a full URL containing protocols or paths is passed.
            # We clean the domain for "domain", and write the raw input into the "website" field.
            clean = website.strip().lower()
            if "://" in clean:
                clean = clean.split("://", 1)[1]
            if "/" in clean:
                clean = clean.split("/", 1)[0]
            if clean.startswith("www."):
                clean = clean[4:]
            payload["properties"]["domain"] = clean
            payload["properties"]["website"] = website
            
        async with httpx.AsyncClient() as client:
            r = await client.post(url, headers=headers, json=payload, timeout=10.0)
            if not r.is_success:
                logger.error("HubSpot company creation failed: Status %s, Response: %s", r.status_code, r.text)
            r.raise_for_status()
            res = r.json()
            return self._normalize_hubspot_company(res)

    async def _create_hubspot_deal(self, token: str, name: str, stage: str, amount: float) -> dict:
        url = "https://api.hubapi.com/crm/v3/objects/deals"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "properties": {
                "dealname": name,
                "dealstage": self._map_deal_stage_to_hubspot(stage),
                "amount": str(amount)
            }
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(url, headers=headers, json=payload, timeout=10.0)
            if not r.is_success:
                logger.error("HubSpot deal creation failed: Status %s, Response: %s", r.status_code, r.text)
            r.raise_for_status()
            res = r.json()
            return self._normalize_hubspot_deal(res)

    def _get_hubspot_assoc_type_id(self, name: str) -> int:
        # Standard HubSpot Association Type IDs
        mapping = {
            "contact_to_note": 202,
            "company_to_note": 190,
            "deal_to_note": 214,
            "contact_to_task": 204,
            "company_to_task": 192,
            "deal_to_task": 216
        }
        return mapping.get(name, 202)

    # --- HubSpot Normalization Helpers ---

    def _normalize_hubspot_contact(self, c: dict) -> dict:
        props = c.get("properties", {})
        return {
            "provider": "hubspot",
            "object_type": "contact",
            "crm_object_id": c["id"],
            "first_name": props.get("firstname") or "",
            "last_name": props.get("lastname") or "",
            "name": f"{props.get('firstname') or ''} {props.get('lastname') or ''}".strip(),
            "email": props.get("email") or "",
            "phone": props.get("phone") or "",
            "owner": {
                "name": "HubSpot Owner ID: " + (props.get("hubspot_owner_id") or "Unassigned"),
                "email": ""
            },
            "related_account": {
                "name": None,  # Fetching association would require a separate lookup
                "id": None
            }
        }

    def _normalize_hubspot_company(self, c: dict) -> dict:
        props = c.get("properties", {})
        return {
            "provider": "hubspot",
            "object_type": "account",
            "crm_object_id": c["id"],
            "name": props.get("name") or "Unnamed Company",
            "industry": props.get("industry"),
            "website": props.get("domain"),
            "owner": {
                "name": "Unassigned",
                "email": ""
            }
        }

    def _normalize_hubspot_deal(self, d: dict) -> dict:
        props = d.get("properties", {})
        amt = 0.0
        try:
            amt = float(props.get("amount") or 0)
        except ValueError:
            pass
            
        return {
            "provider": "hubspot",
            "object_type": "deal",
            "crm_object_id": d["id"],
            "name": props.get("dealname") or "Unnamed Deal",
            "stage": props.get("dealstage") or "Unknown",
            "amount": amt,
            "currency": "USD",
            "close_date": props.get("closedate"),
            "owner": {
                "name": "Unassigned",
                "email": ""
            },
            "related_account": {
                "name": None,
                "id": None
            }
        }


def get_crm_service() -> CRMService:
    return CRMService()
