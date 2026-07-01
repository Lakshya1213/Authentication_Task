"""Service layer for the B2B Call Transcript HubSpot Agent POC."""

import json
import logging
import re
import datetime
import httpx
from sqlalchemy.orm import Session
from config import get_settings
from mcp_server import mcp
from services.crm_service import get_crm_service
from models.sandbox_crm import SandboxAccount, SandboxContact, SandboxDeal, SandboxNote, SandboxTask

logger = logging.getLogger(__name__)

class TranscriptAgentService:
    def __init__(self):
        self.crm_service = get_crm_service()

    async def discover_tools(self) -> list[dict]:
        """Discover available CRM tools registered on the FastMCP instance."""
        try:
            tools = await mcp.list_tools()
            available_tools = []
            for t in tools:
                if t.name.startswith("crm."):
                    available_tools.append({
                        "name": t.name,
                        "description": t.description or "",
                        "input_schema": t.inputSchema or {}
                    })
            return available_tools
        except Exception as e:
            logger.error("Failed to discover MCP tools: %s", e)
            return []

    async def discover_properties(self, db: Session, user_id: int, provider: str) -> dict[str, list[dict]]:
        """Fetch available writable properties for deals, contacts, and companies."""
        p_key = provider.lower()
        token = await self.crm_service._get_valid_token(db, user_id, p_key)
        
        if token.startswith("mock_access_token"):
            # Return hardcoded writable properties for sandbox mode
            return {
                "deals": [
                    {"name": "dealname", "label": "Deal Name", "type": "string", "readOnly": False},
                    {"name": "dealstage", "label": "Deal Stage", "type": "enumeration", "readOnly": False},
                    {"name": "amount", "label": "Amount", "type": "number", "readOnly": False},
                    {"name": "closedate", "label": "Close Date", "type": "datetime", "readOnly": False},
                    {"name": "description", "label": "Description", "type": "string", "readOnly": False}
                ],
                "contacts": [
                    {"name": "firstname", "label": "First Name", "type": "string", "readOnly": False},
                    {"name": "lastname", "label": "Last Name", "type": "string", "readOnly": False},
                    {"name": "email", "label": "Email", "type": "string", "readOnly": False},
                    {"name": "phone", "label": "Phone Number", "type": "string", "readOnly": False},
                    {"name": "jobtitle", "label": "Job Title", "type": "string", "readOnly": False}
                ],
                "companies": [
                    {"name": "name", "label": "Company Name", "type": "string", "readOnly": False},
                    {"name": "industry", "label": "Industry", "type": "enumeration", "readOnly": False},
                    {"name": "domain", "label": "Company Domain", "type": "string", "readOnly": False},
                    {"name": "website", "label": "Website URL", "type": "string", "readOnly": False}
                ]
            }

        # Real API call to HubSpot for each object type
        results = {}
        for obj_type in ["deals", "contacts", "companies"]:
            url = f"https://api.hubapi.com/crm/v3/properties/{obj_type}"
            headers = {"Authorization": f"Bearer {token}"}
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(url, headers=headers, timeout=10.0)
                    r.raise_for_status()
                    data = r.json()
                    props = []
                    allowed_keywords = [
                        "amount", "stage", "date", "name", "desc", "pipeline", "priority", "type", "next", "status",
                        "first", "last", "email", "phone", "title", "role", "industry", "domain", "web"
                    ]
                    for prop in data.get("results", []):
                        if not prop.get("readOnlyValue") and not prop.get("hidden"):
                            name_lower = prop["name"].lower()
                            if not any(kw in name_lower for kw in allowed_keywords):
                                continue
                            props.append({
                                "name": prop["name"],
                                "label": prop["label"],
                                "type": prop["type"],
                                "readOnly": False
                            })
                    results[obj_type] = props
            except Exception as e:
                logger.error("Failed to fetch properties for %s: %s", obj_type, e)
                results[obj_type] = []
        return results

    async def fetch_crm_state_for_deal(self, db: Session, user_id: int, provider: str, deal_id: str) -> dict:
        """Fetch current deal state, associated contacts, associated company, open tasks, and recent notes."""
        p_key = provider.lower()
        token = await self.crm_service._get_valid_token(db, user_id, p_key)
        
        if token.startswith("mock_access_token"):
            # Sandbox lookup
            deal = db.query(SandboxDeal).filter(SandboxDeal.user_id == user_id, SandboxDeal.id == int(deal_id)).one_or_none()
            if not deal:
                return {}
            
            # Contacts
            contacts = []
            if deal.account_id:
                s_contacts = db.query(SandboxContact).filter(SandboxContact.user_id == user_id, SandboxContact.account_id == deal.account_id).all()
                contacts = [self.crm_service.sandbox._normalize_contact(c) for c in s_contacts]
                
            # Company
            company = {}
            if deal.account_id:
                s_company = db.query(SandboxAccount).filter(SandboxAccount.user_id == user_id, SandboxAccount.id == deal.account_id).one_or_none()
                if s_company:
                    company = self.crm_service.sandbox._normalize_account(s_company)
            
            # Tasks and Notes linked to deal
            s_tasks = db.query(SandboxTask).filter(SandboxTask.user_id == user_id, SandboxTask.entity_type == "deal", SandboxTask.entity_id == deal_id).all()
            tasks = [{
                "id": str(t.id),
                "title": t.title,
                "due_date": t.due_date,
                "status": t.status,
                "owner": t.owner_name
            } for t in s_tasks]
            
            s_notes = db.query(SandboxNote).filter(SandboxNote.user_id == user_id, SandboxNote.entity_type == "deal", SandboxNote.entity_id == deal_id).all()
            notes = [{
                "id": str(n.id),
                "text": n.body,
                "created_at": n.created_at.isoformat() if n.created_at else ""
            } for n in s_notes]

            return {
                "current_deal": self.crm_service.sandbox._normalize_deal(deal),
                "associated_contacts": contacts,
                "associated_company": company,
                "existing_tasks": tasks,
                "recent_notes": notes
            }

        # Real HubSpot Mode
        try:
            # 1. Fetch deal properties + basic associations list
            url = f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}?properties=dealname,dealstage,amount,closedate&associations=contacts,companies"
            headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient() as client:
                r = await client.get(url, headers=headers, timeout=10.0)
                r.raise_for_status()
                deal_data = r.json()
                normalized_deal = self.crm_service._normalize_hubspot_deal(deal_data)

                # Extract associated IDs
                assoc_contacts = deal_data.get("associations", {}).get("contacts", {}).get("results", [])
                assoc_companies = deal_data.get("associations", {}).get("companies", {}).get("results", [])

                # 2. Fetch associated contacts
                contacts = []
                for assoc in assoc_contacts[:5]:
                    c_id = assoc["id"]
                    try:
                        c_url = f"https://api.hubapi.com/crm/v3/objects/contacts/{c_id}?properties=firstname,lastname,email,phone"
                        c_r = await client.get(c_url, headers=headers, timeout=5.0)
                        if c_r.status_code == 200:
                            contacts.append(self.crm_service._normalize_hubspot_contact(c_r.json()))
                    except Exception:
                        pass

                # 3. Fetch associated company (first one)
                company = {}
                if assoc_companies:
                    comp_id = assoc_companies[0]["id"]
                    try:
                        comp_url = f"https://api.hubapi.com/crm/v3/objects/companies/{comp_id}?properties=name,industry,domain"
                        comp_r = await client.get(comp_url, headers=headers, timeout=5.0)
                        if comp_r.status_code == 200:
                            company = self.crm_service._normalize_hubspot_company(comp_r.json())
                    except Exception:
                        pass

                # 4. Fetch associated notes
                notes = []
                try:
                    notes_assoc_url = f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}/associations/notes"
                    notes_assoc_r = await client.get(notes_assoc_url, headers=headers, timeout=5.0)
                    if notes_assoc_r.status_code == 200:
                        note_ids = [x["id"] for x in notes_assoc_r.json().get("results", [])]
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
                except Exception:
                    pass

                # 5. Fetch associated tasks
                tasks = []
                try:
                    tasks_assoc_url = f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}/associations/tasks"
                    tasks_assoc_r = await client.get(tasks_assoc_url, headers=headers, timeout=5.0)
                    if tasks_assoc_r.status_code == 200:
                        task_ids = [x["id"] for x in tasks_assoc_r.json().get("results", [])]
                        for tid in task_ids[:5]:
                            t_url = f"https://api.hubapi.com/crm/v3/objects/tasks/{tid}?properties=hs_task_subject,hs_task_status,hs_task_remind_date"
                            t_r = await client.get(t_url, headers=headers, timeout=5.0)
                            if t_r.status_code == 200:
                                td = t_r.json()
                                tasks.append({
                                    "id": td["id"],
                                    "title": td.get("properties", {}).get("hs_task_subject") or "",
                                    "due_date": td.get("properties", {}).get("hs_task_remind_date") or "",
                                    "status": td.get("properties", {}).get("hs_task_status") or "NOT_STARTED",
                                    "owner": "CRM Assignee"
                                })
                except Exception:
                    pass

                return {
                    "current_deal": normalized_deal,
                    "associated_contacts": contacts,
                    "associated_company": company,
                    "existing_tasks": tasks,
                    "recent_notes": notes
                }
        except Exception as e:
            logger.error("Failed to fetch CRM state for deal %s: %s", deal_id, e)
            return {}

    async def call_groq_llm(self, system_prompt: str, user_prompt: str) -> dict:
        """Call Groq API with OpenAI compatibility."""
        settings = get_settings()
        api_key = settings.groq_api_key
        model = settings.groq_model or "openai/gpt-oss-120b"
        
        if not api_key:
            logger.warning("Groq API key not set. Using local mock parsing engine.")
            return {}
            
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }
        
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(url, headers=headers, json=payload, timeout=30.0)
                if r.status_code == 400 and ("model" in r.text or "not found" in r.text.lower()):
                    logger.warning("Groq model %s not available. Falling back to llama-3.3-70b-versatile.", model)
                    payload["model"] = "llama-3.3-70b-versatile"
                    r = await client.post(url, headers=headers, json=payload, timeout=30.0)
                r.raise_for_status()
                data = r.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)
        except Exception as e:
            logger.error("Groq LLM call failed: %s", e)
            return {}

    def run_fallback_extraction(self, transcript: str, properties: dict) -> dict:
        """Fallback regex parser if Groq API key is not configured."""
        logger.info("Executing B2B transcript candidate regex extraction fallback...")
        deal_candidates = []
        task_candidates = []
        note_candidates = []
        
        # 1. Look for Deal Amount changes
        amt_match = re.search(r'(?:deal size|amount|budget|price|value is|pricing is)\s*(?:of|to|around)?\s*\$?\s*(\d{2,3})[,\s]*(\d{3})', transcript, re.IGNORECASE)
        if amt_match:
            val = float(amt_match.group(1) + amt_match.group(2))
            deal_candidates.append({
                "object_type": "deal",
                "property_name": "amount",
                "property_label": "Amount",
                "extracted_value": val,
                "evidence_text": amt_match.group(0)
            })
            
        # 2. Look for Deal Stage changes
        stages_map = {
            "closed won": "closedwon",
            "closed lost": "closedlost",
            "proposal sent": "contractsent",
            "negotiation": "decisionmakerboughtin",
            "needs analysis": "appointmentscheduled",
            "appointment scheduled": "appointmentscheduled"
        }
        for keyword, stage_id in stages_map.items():
            if re.search(rf'(?:move|stage|update|shift|set)\s*(?:the)?\s*(?:deal)?\s*(?:stage)?\s*(?:to)?\s*{keyword}', transcript, re.IGNORECASE):
                deal_candidates.append({
                    "object_type": "deal",
                    "property_name": "dealstage",
                    "property_label": "Deal Stage",
                    "extracted_value": keyword.title(),
                    "evidence_text": f"move to {keyword}"
                })
                break
                
        # 3. Look for Next Step / Description updates
        ns_match = re.search(r'(?:next step|description)\s*is\s*([^.]+)', transcript, re.IGNORECASE)
        if ns_match:
            val = ns_match.group(1).strip()
            deal_candidates.append({
                "object_type": "deal",
                "property_name": "description",
                "property_label": "Description",
                "extracted_value": val,
                "evidence_text": ns_match.group(0)
            })

        # 4. Extract Task candidates
        # E.g. "We need to follow up with John to send the proposal"
        task_phrases = re.findall(r'(?:need to|should|will|let\'s|have to)\s+(follow up|send|share|call|schedule|arrange)\s+([^.\n]+)', transcript, re.IGNORECASE)
        for tp in task_phrases[:3]:
            evidence = f"{tp[0]} {tp[1]}"
            task_candidates.append({
                "title": f"{tp[0].capitalize()} {tp[1]}",
                "due_date": (datetime.date.today() + datetime.timedelta(days=7)).isoformat() + "T12:00:00Z",
                "body": f"Action plan: {tp[0]} {tp[1]}",
                "evidence_text": evidence
            })
            
        # 5. Extract Note candidates
        note_candidates.append({
            "note_body": "Sales call transcript summary: " + transcript[:120].strip() + "...",
            "evidence_text": transcript[:30]
        })

        return {
            "deal_property_candidates": deal_candidates,
            "contact_property_candidates": [],
            "company_property_candidates": [],
            "task_candidates": task_candidates,
            "note_candidates": note_candidates
        }

    def run_fallback_proposal(self, candidates: dict, state: dict, tools: list) -> dict:
        """Fallback rule-based change proposal engine."""
        logger.info("Executing B2B transcript change proposal fallback...")
        proposed = []
        skipped = []
        
        deal_state = state.get("current_deal", {})
        deal_id = deal_state.get("crm_object_id")
        
        # 1. Process Deal Candidates
        for cand in candidates.get("deal_property_candidates", []):
            prop = cand["property_name"]
            proposed_val = cand["extracted_value"]
            curr_val = deal_state.get(prop)
            
            # If dealstage is checked, map it to raw value
            mapped_proposed = proposed_val
            if prop == "dealstage":
                from services.crm_service import get_crm_service
                mapped_proposed = get_crm_service()._map_deal_stage_to_hubspot(str(proposed_val))
            
            # Stage ID normalization comparison
            is_different = True
            if prop == "amount":
                try:
                    is_different = float(curr_val or 0) != float(proposed_val)
                except ValueError:
                    pass
            elif prop == "dealstage":
                is_different = str(curr_val).lower().replace("_", "") != str(mapped_proposed).lower().replace("_", "")
            else:
                is_different = str(curr_val or "").strip().lower() != str(proposed_val).strip().lower()
                
            if is_different:
                # Map to MCP tools
                tool_name = "crm.propose_deal_update"
                payload = {
                    "provider": "hubspot",
                    "deal_id": deal_id,
                    "proposed_changes": json.dumps({prop: proposed_val}),
                    "reason": f"Extracted from transcript: {cand['evidence_text']}"
                }
                proposed.append({
                    "action_type": "update_deal_property",
                    "object_type": "deal",
                    "object_id": deal_id,
                    "property_name": prop,
                    "current_value": curr_val or "Empty",
                    "proposed_value": proposed_val,
                    "reason": f"Discovered changes: {cand['evidence_text']}",
                    "evidence_text": cand["evidence_text"],
                    "tool_to_call": tool_name,
                    "tool_payload": payload
                })
            else:
                skipped.append({
                    "candidate": cand,
                    "reason": f"Property '{prop}' current CRM value is already the same ('{curr_val}')."
                })
                
        # 2. Process Task Candidates
        existing_tasks = state.get("existing_tasks", [])
        for cand in candidates.get("task_candidates", []):
            # Check duplicates
            is_dup = False
            for et in existing_tasks:
                if cand["title"].lower() in et["title"].lower() or et["title"].lower() in cand["title"].lower():
                    is_dup = True
                    break
            if is_dup:
                skipped.append({
                    "candidate": cand,
                    "reason": f"Duplicate task: A similar task '{cand['title']}' already exists on this deal."
                })
            else:
                proposed.append({
                    "action_type": "create_task",
                    "object_type": "task",
                    "associated_deal_id": deal_id,
                    "reason": f"Follow-up required: {cand['evidence_text']}",
                    "evidence_text": cand["evidence_text"],
                    "tool_to_call": "crm.create_task",
                    "tool_payload": {
                        "provider": "hubspot",
                        "entity_type": "deal",
                        "entity_id": deal_id,
                        "task_title": cand["title"],
                        "due_date": cand["due_date"]
                    }
                })
                
        # 3. Process Note Candidates
        for cand in candidates.get("note_candidates", []):
            proposed.append({
                "action_type": "create_note",
                "object_type": "note",
                "associated_deal_id": deal_id,
                "reason": "Useful call context summary.",
                "evidence_text": cand["evidence_text"],
                "tool_to_call": "crm.create_note",
                "tool_payload": {
                    "provider": "hubspot",
                    "entity_type": "deal",
                    "entity_id": deal_id,
                    "note_text": cand["note_body"]
                }
            })
            
        return {
            "proposed_changes": proposed,
            "skipped_candidates": skipped
        }

    async def run_transcript_agent(self, db: Session, user_id: int, provider: str, deal_id: str, transcript: str) -> dict:
        """Run the B2B Call Transcript Agent proposal flow."""
        # 1. Discover available tools
        available_tools = await self.discover_tools()
        
        # 2. Discover available writable properties
        discovered_properties = await self.discover_properties(db, user_id, provider)
        
        # 3. Fetch current CRM state
        current_state = await self.fetch_crm_state_for_deal(db, user_id, provider, deal_id)
        if not current_state:
            raise ValueError(f"Deal ID '{deal_id}' not found in connected CRM provider.")
            
        settings = get_settings()
        api_key = settings.groq_api_key
        
        if not api_key:
            # Run using fallback rule engine
            candidates = self.run_fallback_extraction(transcript, discovered_properties)
            proposal = self.run_fallback_proposal(candidates, current_state, available_tools)
            return {
                "discovered_tools": available_tools,
                "discovered_properties": discovered_properties,
                "extracted_candidates": candidates,
                "current_crm_state": current_state,
                "proposed_changes": proposal["proposed_changes"],
                "skipped_candidates": proposal["skipped_candidates"]
            }

        # Optimize payloads to prevent 413 Payload Too Large
        simplified_properties = {
            obj: [f"{p['label']} (internal name: {p['name']})" for p in props]
            for obj, props in discovered_properties.items()
        }
        simplified_tools = [
            {"name": t["name"], "description": t["description"]}
            for t in available_tools
        ]
        write_tools = [
            t for t in available_tools 
            if t["name"] in ["crm.create_note", "crm.create_task", "crm.propose_deal_update"]
        ]

        # LLM Prompts
        # Prompt 1: Extraction Agent
        system_extraction = """You are a CRM extraction agent.
You will receive:
1. A B2B sales call transcript.
2. Actual HubSpot CRM property definitions.
3. Actual HubSpot MCP tool definitions.

Your job:
Extract only CRM updates that map to actual writable HubSpot properties or valid HubSpot activity objects.

Rules:
- Do not invent CRM fields.
- Do not create new properties.
- Only use property names present in the provided HubSpot property list.
- Do not use read-only properties.
- If useful information does not fit a writable property, create a note candidate.
- If a future action is clearly mentioned, create a task candidate.
- Include short evidence_text from the transcript.
- Return JSON only.

Output JSON Format:
{
  "deal_property_candidates": [
     {"object_type": "deal", "property_name": "name", "property_label": "Label", "extracted_value": "value", "evidence_text": "phrase"}
  ],
  "contact_property_candidates": [],
  "company_property_candidates": [],
  "task_candidates": [
     {"title": "task title", "due_date": "ISO8601 string", "body": "details", "evidence_text": "phrase"}
  ],
  "note_candidates": [
     {"note_body": "note text", "evidence_text": "phrase"}
  ]
}"""

        user_extraction = f"""Sales transcript:
{transcript}

HubSpot CRM properties:
{json.dumps(simplified_properties, indent=2)}

HubSpot MCP tools:
{json.dumps(simplified_tools, indent=2)}"""

        candidates = await self.call_groq_llm(system_extraction, user_extraction)
        if not candidates or "deal_property_candidates" not in candidates:
            # Fallback to rule engine if LLM fails
            candidates = self.run_fallback_extraction(transcript, discovered_properties)

        # Prompt 2: Change Proposal Agent
        system_proposal = """You are a HubSpot CRM change proposal agent.
You will receive:
1. Candidate CRM updates extracted from a transcript.
2. Current HubSpot CRM state.
3. Actual HubSpot MCP tool definitions and input schemas.

Your job:
Decide which CRM changes should be proposed.

Rules:
- Do not directly update CRM.
- Propose only changes that are useful and clearly supported.
- Do not propose duplicate tasks (check current state's existing_tasks).
- Do not update a property if the current value is already the same.
- Do not update fields with weak or unclear evidence.
- Use actual MCP tool names and construct payloads (tool_payload) according to actual tool schemas.
- Return JSON only.

Output JSON Format:
{
  "proposed_changes": [
     {
       "action_type": "update_deal_property",
       "object_type": "deal",
       "object_id": "deal_id_here",
       "property_name": "property_name_here",
       "current_value": "current_value_here",
       "proposed_value": "new_value_here",
       "reason": "explanation",
       "evidence_text": "transcript phrase",
       "tool_to_call": "crm.propose_deal_update",
       "tool_payload": { "provider": "hubspot", "deal_id": "...", "proposed_changes": "JSON string of changes", "reason": "..." }
     }
  ],
  "skipped_candidates": [
     {
       "candidate": {},
       "reason": "why skipped"
     }
  ]
}"""

        user_proposal = f"""Candidate updates:
{json.dumps(candidates, indent=2)}

Current CRM state:
{json.dumps(current_state, indent=2)}

MCP tools and schemas:
{json.dumps(write_tools, indent=2)}"""

        proposal = await self.call_groq_llm(system_proposal, user_proposal)
        if not proposal or "proposed_changes" not in proposal:
            proposal = self.run_fallback_proposal(candidates, current_state, available_tools)

        return {
            "discovered_tools": available_tools,
            "discovered_properties": discovered_properties,
            "extracted_candidates": candidates,
            "current_crm_state": current_state,
            "proposed_changes": proposal.get("proposed_changes", []),
            "skipped_candidates": proposal.get("skipped_candidates", [])
        }

    async def apply_transcript_changes(self, db: Session, user_id: int, provider: str, approved_changes: list[dict]) -> dict:
        """Apply approved transcript updates using HubSpot/sandbox CRM services."""
        executed = []
        failed = []
        
        for change in approved_changes:
            action = change.get("action_type")
            tool_name = change.get("tool_to_call")
            payload = change.get("tool_payload") or {}
            
            try:
                if action == "update_deal_property":
                    # Propose deal update
                    changes = payload.get("proposed_changes")
                    if isinstance(changes, str):
                        changes = json.loads(changes)
                    res = await self.crm_service.propose_deal_update(
                        db, user_id, provider, payload.get("deal_id"), changes, payload.get("reason")
                    )
                    executed.append(f"Proposed deal property change: {payload.get('proposed_changes')}")
                elif action == "create_task":
                    # Create follow-up task
                    res = await self.crm_service.create_task(
                        db, user_id, provider, payload.get("entity_type"), payload.get("entity_id"),
                        payload.get("task_title"), payload.get("due_date")
                    )
                    executed.append(f"Created task: '{payload.get('task_title')}'")
                elif action == "create_note":
                    # Create note
                    res = await self.crm_service.create_note(
                        db, user_id, provider, payload.get("entity_type"), payload.get("entity_id"),
                        payload.get("note_text")
                    )
                    executed.append("Created meeting note on deal")
                else:
                    failed.append(f"Unsupported action type: {action}")
            except Exception as e:
                logger.error("Failed to execute change %s: %s", change, e)
                failed.append(f"Failed to execute {action}: {str(e)}")
                
        return {
            "executed": executed,
            "failed": failed,
            "summary": f"Successfully applied {len(executed)} changes. {len(failed)} failed."
        }
