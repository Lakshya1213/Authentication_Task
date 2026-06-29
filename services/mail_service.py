import base64
import logging
import re
from datetime import UTC, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr
import httpx
from sqlalchemy.orm import Session

from models.audit_log import AuditLog
from models.connected_account import ConnectedAccount
from models.user import User
from schemas.mail_schema import EmailAddress, NormalizedMail
from services.oauth_service import get_oauth_service, OAuthError
from utils.encryption import decrypt_token

logger = logging.getLogger(__name__)


class MailService:
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

        now_utc = datetime.now(UTC)
        is_expired = token.expires_at is None or token.expires_at <= now_utc + timedelta(seconds=60)

        if is_expired:
            logger.info("Google access token is expired or close to expiring. Refreshing...")
            try:
                await self.oauth_service.refresh_access_token(db, user_id=user_id, provider="google")
                db.refresh(token)
            except Exception as exc:
                logger.exception("Failed to refresh Google token automatically")
                account.status = "expired"
                db.commit()
                raise OAuthError("Unable to refresh Google access token", error_type="token_refresh_failed") from exc

        try:
            return decrypt_token(token.encrypted_access_token)
        except Exception as exc:
            logger.exception("Token decryption failed")
            raise OAuthError("Failed to decrypt access token", error_type="encryption_error") from exc

    def _log_audit(self, db: Session, user_id: int, action: str, status: str) -> None:
        """Create a mail audit log entry."""
        try:
            log = AuditLog(
                user_id=user_id,
                action=action,
                provider="gmail",
                status=status,
            )
            db.add(log)
            db.commit()
        except Exception:
            logger.exception("Failed to write mail audit log")

    def _strip_html(self, html_content: str) -> str:
        """Helper to strip HTML tags and decode common entities."""
        if not html_content:
            return ""
        # Remove script and style elements
        text = re.sub(r'<(script|style)\b[^>]*>([\s\S]*?)<\/\1>', '', html_content, flags=re.I)
        # Remove tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Replace multiple spaces/newlines
        text = re.sub(r'\s+', ' ', text).strip()
        # Decode common HTML entities
        text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#039;", "'")
        return text

    def _parse_email_address(self, header_val: str) -> EmailAddress:
        """Parse raw email address header into EmailAddress schema."""
        if not header_val:
            return EmailAddress(name="", email="")
        name, email = parseaddr(header_val)
        return EmailAddress(name=name or email, email=email)

    def _parse_multiple_email_addresses(self, header_val: str) -> list[EmailAddress]:
        """Parse header values containing multiple email addresses."""
        if not header_val:
            return []
        parts = header_val.split(",")
        addresses = []
        for part in parts:
            name, email = parseaddr(part)
            if email:
                addresses.append(EmailAddress(name=name or email, email=email))
        return addresses

    def _get_header_value(self, headers: list[dict], name: str) -> str:
        """Get the value of a header from the Gmail headers list."""
        for h in headers:
            if h.get("name", "").lower() == name.lower():
                return h.get("value", "")
        return ""

    def _parse_gmail_body(self, payload: dict) -> str:
        """Recursively decode and extract the text/plain or text/html body from Gmail payload."""
        def decode_b64(data):
            if not data:
                return ""
            padding = '=' * (4 - len(data) % 4)
            try:
                return base64.urlsafe_b64decode(data + padding).decode('utf-8', errors='ignore')
            except Exception:
                return ""

        if "parts" in payload:
            text_body = ""
            html_body = ""
            for part in payload["parts"]:
                mime_type = part.get("mimeType", "")
                if mime_type == "text/plain":
                    text_body += decode_b64(part.get("body", {}).get("data", ""))
                elif mime_type == "text/html":
                    html_body += decode_b64(part.get("body", {}).get("data", ""))
                elif "parts" in part:
                    nested_text = self._parse_gmail_body(part)
                    if nested_text:
                        text_body += nested_text
            return text_body or self._strip_html(html_body)
        else:
            body_data = payload.get("body", {}).get("data", "")
            decoded = decode_b64(body_data)
            if payload.get("mimeType") == "text/html":
                return self._strip_html(decoded)
            return decoded

    def _check_has_attachments(self, payload: dict) -> bool:
        """Recursively check if the payload contains attachments."""
        if not payload:
            return False
        if payload.get("filename"):
            return True
        for part in payload.get("parts", []):
            if self._check_has_attachments(part):
                return True
        return False

    def _normalize_gmail_message(self, msg: dict) -> NormalizedMail:
        """Map raw Gmail API message resource to NormalizedMail."""
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])

        from_val = self._get_header_value(headers, "From")
        to_val = self._get_header_value(headers, "To")
        subject = self._get_header_value(headers, "Subject") or "(No Subject)"
        
        # Get received time from internalDate (ms timestamp)
        internal_date = msg.get("internalDate")
        if internal_date:
            dt = datetime.fromtimestamp(int(internal_date) / 1000.0, tz=UTC)
            received_at = dt.isoformat()
        else:
            received_at = datetime.now(UTC).isoformat()

        body_text = self._parse_gmail_body(payload)
        snippet = msg.get("snippet", "") or (body_text[:100] + "..." if body_text else "")

        return NormalizedMail(
            provider="gmail",
            message_id=msg.get("id"),
            thread_id=msg.get("threadId"),
            from_=self._parse_email_address(from_val),
            to=self._parse_multiple_email_addresses(to_val),
            subject=subject,
            received_at=received_at,
            snippet=snippet,
            body_text=body_text or snippet,
            has_attachments=self._check_has_attachments(payload),
        )

    def is_internal_or_test_email(self, db: Session, email: str, user_email: str) -> bool:
        """Enforces safety whitelisting rules: user's own email, registered users, @example.com, @test.com, or localhost."""
        email = email.lower().strip()
        user_email = user_email.lower().strip()
        if not email:
            return False
        if email == user_email:
            return True
        try:
            registered_emails = {u.email.lower().strip() for u in db.query(User).all()}
            if email in registered_emails:
                return True
        except Exception:
            logger.exception("Failed to query registered users for whitelist")
        if email.endswith("@example.com") or email.endswith("@test.com") or email.endswith(".local") or email.endswith("@localhost.localdomain"):
            return True
        return False

    async def search_messages(self, db: Session, user_id: int, query: str, limit: int = 10, provider: str = "gmail") -> list[NormalizedMail]:
        """Search Gmail messages applying optional search filters."""
        access_token = await self._get_google_token_with_fallback(db, user_id, provider)

        url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
        params = {"maxResults": limit}
        if query:
            params["q"] = query

        async with httpx.AsyncClient() as client:
            try:
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(url, headers=headers, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                logger.exception("Gmail list messages API call failed")
                self._log_audit(db, user_id, "search_messages", "failed")
                raise OAuthError("Failed to fetch emails from Gmail", error_type="api_error") from exc

        messages_meta = data.get("messages", [])
        normalized_messages = []

        # Fetch detailed message information
        # To avoid rate limits or extremely slow responses, fetch sequentially or concurrently up to limit
        for meta in messages_meta[:limit]:
            msg_id = meta["id"]
            try:
                msg_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}"
                async with httpx.AsyncClient() as client:
                    msg_resp = await client.get(msg_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=10.0)
                    msg_resp.raise_for_status()
                    msg_data = msg_resp.json()
                    normalized_messages.append(self._normalize_gmail_message(msg_data))
            except Exception:
                logger.warning("Failed to fetch Gmail message detail for id=%s", msg_id)

        self._log_audit(db, user_id, "search_messages", "success")
        return normalized_messages

    async def read_message(self, db: Session, user_id: int, message_id: str, provider: str = "gmail") -> NormalizedMail:
        """Fetch detailed information and body for a single email."""
        access_token = await self._get_google_token_with_fallback(db, user_id, provider)

        url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"

        async with httpx.AsyncClient() as client:
            try:
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(url, headers=headers, timeout=10.0)
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                logger.exception("Gmail get message API call failed for message_id=%s", message_id)
                self._log_audit(db, user_id, f"read_message:{message_id}", "failed")
                raise OAuthError(f"Failed to retrieve email {message_id} from Gmail", error_type="api_error") from exc

        normalized = self._normalize_gmail_message(data)
        self._log_audit(db, user_id, f"read_message:{message_id}", "success")
        return normalized

    def _build_mime(self, to: str, cc: str | None, subject: str, body: str, thread_id: str | None = None, in_reply_to: str | None = None) -> str:
        """Construct a base64url encoded MIME email."""
        if cc:
            msg = MIMEMultipart()
            msg.attach(MIMEText(body, "plain"))
            msg["Cc"] = cc
        else:
            msg = MIMEText(body, "plain")

        msg["To"] = to
        msg["Subject"] = subject
        
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            msg["References"] = in_reply_to

        raw_bytes = msg.as_bytes()
        return base64.urlsafe_b64encode(raw_bytes).decode("utf-8")

    async def create_draft(self, db: Session, user_id: int, to: str, cc: str | None, subject: str, body: str, provider: str = "gmail") -> dict:
        """Create a new email draft in Gmail."""
        access_token = await self._get_google_token_with_fallback(db, user_id, provider)

        url = "https://gmail.googleapis.com/gmail/v1/users/me/drafts"
        raw_mime = self._build_mime(to, cc, subject, body)

        body_payload = {
            "message": {
                "raw": raw_mime
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                }
                response = await client.post(url, headers=headers, json=body_payload, timeout=10.0)
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                logger.exception("Gmail create draft API call failed")
                self._log_audit(db, user_id, "create_draft", "failed")
                raise OAuthError("Failed to create draft in Gmail", error_type="api_error") from exc

        self._log_audit(db, user_id, "create_draft", "success")
        return {
            "draft_id": data.get("id"),
            "status": "draft_created"
        }

    async def send_message(self, db: Session, user_id: int, to: str, cc: str | None, subject: str, body: str, provider: str = "gmail", confirmation_required: bool = True) -> dict:
        """Send a new email, verifying the recipient and confirmation rules."""
        # Retrieve user email
        user = db.query(User).filter(User.id == user_id).one_or_none()
        user_email = user.email if user else ""

        # Enforce recipient whitelist
        if not self.is_internal_or_test_email(db, to, user_email):
            logger.warning("Email blocked: recipient %s is not an internal or test address.", to)
            self._log_audit(db, user_id, f"send_message:blocked:{to}", "blocked")
            return {
                "status": "blocked",
                "message": f"Sending to '{to}' is blocked. You can only send to internal or test email addresses for safety."
            }

        # Handle CC recipient checks as well
        if cc:
            cc_list = [addr.strip() for addr in cc.split(",") if addr.strip()]
            for cc_addr in cc_list:
                if not self.is_internal_or_test_email(db, cc_addr, user_email):
                    logger.warning("Email blocked: CC recipient %s is not an internal or test address.", cc_addr)
                    self._log_audit(db, user_id, f"send_message:blocked:{cc_addr}", "blocked")
                    return {
                        "status": "blocked",
                        "message": f"Sending to CC '{cc_addr}' is blocked. CC recipients must also be internal or test email addresses."
                    }

        # If confirmation is required, create a draft first and return confirmation_required status
        if confirmation_required:
            logger.info("Email to %s requires user confirmation. Saving as draft.", to)
            draft_res = await self.create_draft(db, user_id, to, cc, subject, body, provider)
            self._log_audit(db, user_id, "send_message:confirmation_required", "confirmation_required")
            return {
                "status": "confirmation_required",
                "draft_id": draft_res["draft_id"],
                "message": "Email draft created. Explicit user confirmation is required to send this email."
            }

        # Send email directly (after explicit confirmation flag is overridden or set to False)
        access_token = await self._get_google_token_with_fallback(db, user_id, provider)
        url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
        raw_mime = self._build_mime(to, cc, subject, body)

        body_payload = {
            "raw": raw_mime
        }

        async with httpx.AsyncClient() as client:
            try:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                }
                response = await client.post(url, headers=headers, json=body_payload, timeout=10.0)
                response.raise_for_status()
            except Exception as exc:
                logger.exception("Gmail send message API call failed")
                self._log_audit(db, user_id, "send_message", "failed")
                raise OAuthError("Failed to send email in Gmail", error_type="api_error") from exc

        self._log_audit(db, user_id, "send_message", "success")
        return {
            "status": "sent",
            "message": "Email sent successfully!"
        }

    async def reply_to_message(self, db: Session, user_id: int, message_id: str, body: str, provider: str = "gmail") -> dict:
        """Reply to an email thread by creating a reply draft."""
        # 1. Fetch original message
        orig_msg = await self.read_message(db, user_id, message_id, provider)

        # Retrieve user email
        user = db.query(User).filter(User.id == user_id).one_or_none()
        user_email = user.email if user else ""

        # 2. Recipient is the sender of the original message
        recipient = orig_msg.from_.email
        if not self.is_internal_or_test_email(db, recipient, user_email):
            logger.warning("Reply blocked: original sender %s is not whitelisted.", recipient)
            self._log_audit(db, user_id, f"reply_to_message:blocked:{recipient}", "blocked")
            return {
                "status": "blocked",
                "message": f"Replying to '{recipient}' is blocked. You can only reply to internal or test email addresses."
            }

        # 3. Construct Subject: prefix with "Re: " if not present
        orig_subject = orig_msg.subject
        subject = orig_subject if orig_subject.lower().startswith("re:") else f"Re: {orig_subject}"

        # 4. Fetch the original raw message to find Message-ID header (for In-Reply-To / References)
        access_token = await self._get_google_token_with_fallback(db, user_id, provider)
        url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"
        
        async with httpx.AsyncClient() as client:
            try:
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(url, headers=headers, timeout=10.0)
                response.raise_for_status()
                raw_data = response.json()
            except Exception as exc:
                logger.exception("Failed to get raw message for replying")
                self._log_audit(db, user_id, f"reply_to_message:failed_read:{message_id}", "failed")
                raise OAuthError("Failed to reply: original message headers could not be retrieved.", error_type="api_error") from exc

        orig_headers = raw_data.get("payload", {}).get("headers", [])
        orig_message_id = self._get_header_value(orig_headers, "Message-ID")

        # 5. Build MIME message with proper thread references
        raw_mime = self._build_mime(
            to=recipient,
            cc=None,
            subject=subject,
            body=body,
            thread_id=orig_msg.thread_id,
            in_reply_to=orig_message_id or None
        )

        # 6. Create Draft inside the thread
        draft_url = "https://gmail.googleapis.com/gmail/v1/users/me/drafts"
        draft_payload = {
            "message": {
                "raw": raw_mime,
                "threadId": orig_msg.thread_id
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                }
                draft_resp = await client.post(draft_url, headers=headers, json=draft_payload, timeout=10.0)
                draft_resp.raise_for_status()
                draft_data = draft_resp.json()
            except Exception as exc:
                logger.exception("Gmail create draft reply API call failed")
                self._log_audit(db, user_id, "reply_to_message", "failed")
                raise OAuthError("Failed to create reply draft in Gmail", error_type="api_error") from exc

        self._log_audit(db, user_id, "reply_to_message", "success")
        return {
            "status": "draft_created",
            "draft_id": draft_data.get("id"),
            "message_id": message_id
        }

    async def send_draft(self, db: Session, user_id: int, draft_id: str, provider: str = "gmail") -> dict:
        """Send a pre-created email draft (used in confirmation sending flows)."""
        access_token = await self._get_google_token_with_fallback(db, user_id, provider)

        # 1. Fetch draft info to verify safety rules
        draft_url = f"https://gmail.googleapis.com/gmail/v1/users/me/drafts/{draft_id}"
        async with httpx.AsyncClient() as client:
            try:
                headers = {"Authorization": f"Bearer {access_token}"}
                draft_resp = await client.get(draft_url, headers=headers, timeout=10.0)
                draft_resp.raise_for_status()
                draft_data = draft_resp.json()
            except Exception as exc:
                logger.exception("Failed to retrieve draft details for sending")
                self._log_audit(db, user_id, f"send_draft:failed_fetch:{draft_id}", "failed")
                raise OAuthError("Draft not found or could not be verified.", error_type="api_error") from exc

        message_data = draft_data.get("message", {})
        payload = message_data.get("payload", {})
        headers_list = payload.get("headers", [])

        to_val = self._get_header_value(headers_list, "To")
        cc_val = self._get_header_value(headers_list, "Cc")

        # Retrieve user email
        user = db.query(User).filter(User.id == user_id).one_or_none()
        user_email = user.email if user else ""

        # Enforce whitelisting on TO address
        if to_val:
            to_addrs = self._parse_multiple_email_addresses(to_val)
            for addr in to_addrs:
                if not self.is_internal_or_test_email(db, addr.email, user_email):
                    logger.warning("Send draft blocked: recipient %s is not whitelisted.", addr.email)
                    self._log_audit(db, user_id, f"send_draft:blocked:{addr.email}", "blocked")
                    return {
                        "status": "blocked",
                        "message": f"Sending to '{addr.email}' is blocked. You can only send to internal or test email addresses."
                    }

        # Enforce whitelisting on CC address
        if cc_val:
            cc_addrs = self._parse_multiple_email_addresses(cc_val)
            for addr in cc_addrs:
                if not self.is_internal_or_test_email(db, addr.email, user_email):
                    logger.warning("Send draft blocked: CC recipient %s is not whitelisted.", addr.email)
                    self._log_audit(db, user_id, f"send_draft:blocked:{addr.email}", "blocked")
                    return {
                        "status": "blocked",
                        "message": f"Sending to CC '{addr.email}' is blocked. CC recipients must also be internal or test email addresses."
                    }

        # 2. Send Draft
        send_url = "https://gmail.googleapis.com/gmail/v1/users/me/drafts/send"
        send_payload = {
            "id": draft_id
        }

        async with httpx.AsyncClient() as client:
            try:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                }
                response = await client.post(send_url, headers=headers, json=send_payload, timeout=10.0)
                response.raise_for_status()
            except Exception as exc:
                logger.exception("Gmail send draft API call failed")
                self._log_audit(db, user_id, "send_draft", "failed")
                raise OAuthError("Failed to send draft in Gmail", error_type="api_error") from exc

        self._log_audit(db, user_id, "send_draft", "success")
        return {
            "status": "sent",
            "message": "Draft sent successfully!"
        }

    async def _get_google_token_with_fallback(self, db: Session, user_id: int, provider: str) -> str:
        """Retrieve token, handles mapping 'gmail' provider names to 'google' in db."""
        db_provider = "google" if provider.lower() in ("gmail", "google") else provider.lower()
        if db_provider != "google":
            raise OAuthError(f"Unsupported mail provider: {provider}", error_type="unsupported_provider")
        return await self._get_valid_google_token(db, user_id)


def get_mail_service() -> MailService:
    """FastAPI dependency for the Mail service."""
    return MailService()
