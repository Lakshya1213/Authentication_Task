"""Sandbox CRM Service — mocks CRM operations using local database tables."""

import logging
from sqlalchemy import or_
from sqlalchemy.orm import Session
from models.sandbox_crm import SandboxAccount, SandboxContact, SandboxDeal, SandboxNote, SandboxTask

logger = logging.getLogger(__name__)


class SandboxCRMService:
    def seed_sandbox_if_empty(self, db: Session, user_id: int, provider: str) -> None:
        """Seed the local database with mock CRM data for this user/provider if empty."""
        provider_key = provider.lower()
        
        # Check if already seeded
        count = db.query(SandboxAccount).filter(
            SandboxAccount.user_id == user_id,
            SandboxAccount.provider == provider_key
        ).count()
        
        if count > 0:
            return

        logger.info("Seeding sandbox CRM data for user_id=%s provider=%s", user_id, provider_key)
        
        # 1. Seed Accounts
        acme = SandboxAccount(
            user_id=user_id,
            provider=provider_key,
            name="Acme Corp",
            industry="Manufacturing",
            website="https://acme.com",
            owner_name="Alice Johnson",
            owner_email="alice.johnson@example.com"
        )
        tech_sol = SandboxAccount(
            user_id=user_id,
            provider=provider_key,
            name="Tech Solutions",
            industry="Software",
            website="https://techsolutions.io",
            owner_name="Marcus Vance",
            owner_email="marcus.vance@example.com"
        )
        global_ret = SandboxAccount(
            user_id=user_id,
            provider=provider_key,
            name="Global Retail Group",
            industry="Retail",
            website="https://globalretail.com",
            owner_name="Sarah Jenkins",
            owner_email="sarah.jenkins@example.com"
        )
        db.add_all([acme, tech_sol, global_ret])
        db.flush()  # Populates IDs

        # 2. Seed Contacts
        contacts = [
            SandboxContact(
                user_id=user_id,
                provider=provider_key,
                first_name="John",
                last_name="Miller",
                email="john.miller@acme.com",
                phone="+1-555-0101",
                account_id=acme.id,
                owner_name="Alice Johnson",
                owner_email="alice.johnson@example.com"
            ),
            SandboxContact(
                user_id=user_id,
                provider=provider_key,
                first_name="Jane",
                last_name="Doe",
                email="jane.doe@techsolutions.io",
                phone="+1-555-0144",
                account_id=tech_sol.id,
                owner_name="Marcus Vance",
                owner_email="marcus.vance@example.com"
            ),
            SandboxContact(
                user_id=user_id,
                provider=provider_key,
                first_name="Charlie",
                last_name="Smith",
                email="charlie.smith@globalretail.com",
                phone="+1-555-0199",
                account_id=global_ret.id,
                owner_name="Sarah Jenkins",
                owner_email="sarah.jenkins@example.com"
            )
        ]
        db.add_all(contacts)

        # 3. Seed Deals
        deals = [
            SandboxDeal(
                user_id=user_id,
                provider=provider_key,
                name="Acme Corp Annual Renewal",
                stage="Proposal Sent",
                amount=75000.00,
                currency="USD",
                close_date="2026-08-31",
                account_id=acme.id,
                owner_name="Alice Johnson",
                owner_email="alice.johnson@example.com"
            ),
            SandboxDeal(
                user_id=user_id,
                provider=provider_key,
                name="Tech Solutions Pilot",
                stage="Negotiation",
                amount=25000.00,
                currency="USD",
                close_date="2026-07-20",
                account_id=tech_sol.id,
                owner_name="Marcus Vance",
                owner_email="marcus.vance@example.com"
            ),
            SandboxDeal(
                user_id=user_id,
                provider=provider_key,
                name="Global Retail Platform Expansion",
                stage="Closed Won",
                amount=145000.00,
                currency="USD",
                close_date="2026-06-30",
                account_id=global_ret.id,
                owner_name="Sarah Jenkins",
                owner_email="sarah.jenkins@example.com"
            )
        ]
        db.add_all(deals)
        db.commit()
        logger.info("Successfully seeded sandbox CRM data")

    def search_contacts(self, db: Session, user_id: int, query: str, provider: str | None = None) -> list[dict]:
        """Search contacts in the sandbox database."""
        if provider:
            self.seed_sandbox_if_empty(db, user_id, provider)
            
        q = db.query(SandboxContact).filter(SandboxContact.user_id == user_id)
        if provider:
            q = q.filter(SandboxContact.provider == provider.lower())
            
        if query:
            search_pattern = f"%{query}%"
            q = q.filter(
                or_(
                    SandboxContact.first_name.like(search_pattern),
                    SandboxContact.last_name.like(search_pattern),
                    SandboxContact.email.like(search_pattern),
                    SandboxContact.phone.like(search_pattern)
                )
            )
            
        contacts = q.all()
        return [self._normalize_contact(c) for c in contacts]

    def get_contact(self, db: Session, user_id: int, provider: str, contact_id: str) -> dict | None:
        """Fetch details for a contact."""
        self.seed_sandbox_if_empty(db, user_id, provider)
        try:
            cid = int(contact_id)
        except ValueError:
            return None
            
        c = db.query(SandboxContact).filter(
            SandboxContact.user_id == user_id,
            SandboxContact.provider == provider.lower(),
            SandboxContact.id == cid
        ).one_or_none()
        
        if not c:
            return None
            
        # Fetch related notes and tasks
        notes = db.query(SandboxNote).filter(
            SandboxNote.user_id == user_id,
            SandboxNote.provider == provider.lower(),
            SandboxNote.entity_type == "contact",
            SandboxNote.entity_id == str(c.id)
        ).all()
        
        tasks = db.query(SandboxTask).filter(
            SandboxTask.user_id == user_id,
            SandboxTask.provider == provider.lower(),
            SandboxTask.entity_type == "contact",
            SandboxTask.entity_id == str(c.id)
        ).all()

        res = self._normalize_contact(c)
        res["notes"] = [{"id": n.id, "text": n.note_text, "created_at": n.created_at.isoformat()} for n in notes]
        res["tasks"] = [{"id": t.id, "title": t.title, "due_date": t.due_date, "owner": t.owner_name} for t in tasks]
        return res

    def search_accounts(self, db: Session, user_id: int, query: str, provider: str | None = None) -> list[dict]:
        """Search accounts in sandbox."""
        if provider:
            self.seed_sandbox_if_empty(db, user_id, provider)
            
        q = db.query(SandboxAccount).filter(SandboxAccount.user_id == user_id)
        if provider:
            q = q.filter(SandboxAccount.provider == provider.lower())
            
        if query:
            search_pattern = f"%{query}%"
            q = q.filter(
                or_(
                    SandboxAccount.name.like(search_pattern),
                    SandboxAccount.industry.like(search_pattern),
                    SandboxAccount.website.like(search_pattern)
                )
            )
            
        accounts = q.all()
        return [self._normalize_account(acc) for acc in accounts]

    def get_account(self, db: Session, user_id: int, provider: str, account_id: str) -> dict | None:
        """Fetch details for an account."""
        self.seed_sandbox_if_empty(db, user_id, provider)
        try:
            aid = int(account_id)
        except ValueError:
            return None
            
        acc = db.query(SandboxAccount).filter(
            SandboxAccount.user_id == user_id,
            SandboxAccount.provider == provider.lower(),
            SandboxAccount.id == aid
        ).one_or_none()
        
        if not acc:
            return None

        notes = db.query(SandboxNote).filter(
            SandboxNote.user_id == user_id,
            SandboxNote.provider == provider.lower(),
            SandboxNote.entity_type == "account",
            SandboxNote.entity_id == str(acc.id)
        ).all()
        
        tasks = db.query(SandboxTask).filter(
            SandboxTask.user_id == user_id,
            SandboxTask.provider == provider.lower(),
            SandboxTask.entity_type == "account",
            SandboxTask.entity_id == str(acc.id)
        ).all()

        res = self._normalize_account(acc)
        res["notes"] = [{"id": n.id, "text": n.note_text, "created_at": n.created_at.isoformat()} for n in notes]
        res["tasks"] = [{"id": t.id, "title": t.title, "due_date": t.due_date, "owner": t.owner_name} for t in tasks]
        return res

    def search_deals(self, db: Session, user_id: int, query: str, provider: str | None = None) -> list[dict]:
        """Search deals in sandbox."""
        if provider:
            self.seed_sandbox_if_empty(db, user_id, provider)
            
        q = db.query(SandboxDeal).filter(SandboxDeal.user_id == user_id)
        if provider:
            q = q.filter(SandboxDeal.provider == provider.lower())
            
        if query:
            search_pattern = f"%{query}%"
            q = q.filter(
                or_(
                    SandboxDeal.name.like(search_pattern),
                    SandboxDeal.stage.like(search_pattern)
                )
            )
            
        deals = q.all()
        return [self._normalize_deal(d) for d in deals]

    def get_deal(self, db: Session, user_id: int, provider: str, deal_id: str) -> dict | None:
        """Fetch details for a deal."""
        self.seed_sandbox_if_empty(db, user_id, provider)
        try:
            did = int(deal_id)
        except ValueError:
            return None
            
        d = db.query(SandboxDeal).filter(
            SandboxDeal.user_id == user_id,
            SandboxDeal.provider == provider.lower(),
            SandboxDeal.id == did
        ).one_or_none()
        
        if not d:
            return None

        notes = db.query(SandboxNote).filter(
            SandboxNote.user_id == user_id,
            SandboxNote.provider == provider.lower(),
            SandboxNote.entity_type == "deal",
            SandboxNote.entity_id == str(d.id)
        ).all()
        
        tasks = db.query(SandboxTask).filter(
            SandboxTask.user_id == user_id,
            SandboxTask.provider == provider.lower(),
            SandboxTask.entity_type == "deal",
            SandboxTask.entity_id == str(d.id)
        ).all()

        res = self._normalize_deal(d)
        res["notes"] = [{"id": n.id, "text": n.note_text, "created_at": n.created_at.isoformat()} for n in notes]
        res["tasks"] = [{"id": t.id, "title": t.title, "due_date": t.due_date, "owner": t.owner_name} for t in tasks]
        return res

    def create_note(self, db: Session, user_id: int, provider: str, entity_type: str, entity_id: str, note_text: str) -> dict:
        """Add a note to an entity."""
        self.seed_sandbox_if_empty(db, user_id, provider)
        note = SandboxNote(
            user_id=user_id,
            provider=provider.lower(),
            entity_type=entity_type.lower(),
            entity_id=entity_id,
            note_text=note_text
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        return {
            "status": "success",
            "message": "note_created",
            "note_id": note.id,
            "entity_type": entity_type,
            "entity_id": entity_id
        }

    def create_task(self, db: Session, user_id: int, provider: str, entity_type: str, entity_id: str, title: str, due_date: str | None, owner_name: str | None) -> dict:
        """Create a follow-up task."""
        self.seed_sandbox_if_empty(db, user_id, provider)
        task = SandboxTask(
            user_id=user_id,
            provider=provider.lower(),
            entity_type=entity_type.lower(),
            entity_id=entity_id,
            title=title,
            due_date=due_date,
            owner_name=owner_name or "Sales Rep"
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return {
            "status": "success",
            "message": "task_created",
            "task_id": task.id,
            "entity_type": entity_type,
            "entity_id": entity_id
        }

    def update_deal(self, db: Session, user_id: int, provider: str, deal_id: str, updates: dict) -> dict:
        """Directly update deal properties (used once update proposal is approved)."""
        self.seed_sandbox_if_empty(db, user_id, provider)
        try:
            did = int(deal_id)
        except ValueError:
            return {"status": "failed", "message": "invalid_deal_id"}
            
        d = db.query(SandboxDeal).filter(
            SandboxDeal.user_id == user_id,
            SandboxDeal.provider == provider.lower(),
            SandboxDeal.id == did
        ).one_or_none()
        
        if not d:
            return {"status": "failed", "message": "deal_not_found"}

        for key, val in updates.items():
            if hasattr(d, key):
                setattr(d, key, val)
                
        db.commit()
        return {"status": "success", "message": "deal_updated", "deal": self._normalize_deal(d)}

    def create_contact(self, db: Session, user_id: int, provider: str, first_name: str, last_name: str, email: str, phone: str | None = None) -> dict:
        self.seed_sandbox_if_empty(db, user_id, provider)
        p_key = provider.lower()
        contact = SandboxContact(
            user_id=user_id,
            provider=p_key,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            owner_name="Alice Johnson",
            owner_email="alice.johnson@example.com"
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)
        return self._normalize_contact(contact)

    def create_account(self, db: Session, user_id: int, provider: str, name: str, industry: str | None = None, website: str | None = None) -> dict:
        self.seed_sandbox_if_empty(db, user_id, provider)
        p_key = provider.lower()
        acc = SandboxAccount(
            user_id=user_id,
            provider=p_key,
            name=name,
            industry=industry,
            website=website,
            owner_name="Alice Johnson",
            owner_email="alice.johnson@example.com"
        )
        db.add(acc)
        db.commit()
        db.refresh(acc)
        return self._normalize_account(acc)

    def create_deal(self, db: Session, user_id: int, provider: str, name: str, stage: str, amount: float) -> dict:
        self.seed_sandbox_if_empty(db, user_id, provider)
        p_key = provider.lower()
        deal = SandboxDeal(
            user_id=user_id,
            provider=p_key,
            name=name,
            stage=stage,
            amount=amount,
            currency="USD",
            owner_name="Alice Johnson",
            owner_email="alice.johnson@example.com"
        )
        db.add(deal)
        db.commit()
        db.refresh(deal)
        return self._normalize_deal(deal)

    # Normalization helpers
    def _normalize_contact(self, c: SandboxContact) -> dict:
        return {
            "provider": c.provider,
            "object_type": "contact",
            "crm_object_id": str(c.id),
            "first_name": c.first_name,
            "last_name": c.last_name,
            "name": f"{c.first_name} {c.last_name}",
            "email": c.email,
            "phone": c.phone,
            "owner": {
                "name": c.owner_name,
                "email": c.owner_email
            },
            "related_account": {
                "name": c.account.name if c.account else None,
                "id": str(c.account_id) if c.account_id else None
            }
        }

    def _normalize_account(self, acc: SandboxAccount) -> dict:
        return {
            "provider": acc.provider,
            "object_type": "account",
            "crm_object_id": str(acc.id),
            "name": acc.name,
            "industry": acc.industry,
            "website": acc.website,
            "owner": {
                "name": acc.owner_name,
                "email": acc.owner_email
            }
        }

    def _normalize_deal(self, d: SandboxDeal) -> dict:
        return {
            "provider": d.provider,
            "object_type": "deal",
            "crm_object_id": str(d.id),
            "name": d.name,
            "stage": d.stage,
            "amount": d.amount,
            "currency": d.currency,
            "close_date": d.close_date,
            "owner": {
                "name": d.owner_name,
                "email": d.owner_email
            },
            "related_account": {
                "name": d.account.name if d.account else None,
                "id": str(d.account_id) if d.account_id else None
            }
        }
