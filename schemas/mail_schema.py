from pydantic import BaseModel, Field


class EmailAddress(BaseModel):
    name: str | None = None
    email: str


class NormalizedMail(BaseModel):
    provider: str
    message_id: str
    thread_id: str
    from_: EmailAddress = Field(..., alias="from")
    to: list[EmailAddress] = []
    subject: str
    received_at: str
    snippet: str | None = None
    body_text: str | None = None
    has_attachments: bool = False

    class Config:
        populate_by_name = True


class MailDraftCreate(BaseModel):
    to: str
    cc: str | None = None
    subject: str = ""
    body: str = ""
    provider: str | None = "gmail"


class MailDraftResponse(BaseModel):
    draft_id: str
    status: str


class MailSendRequest(BaseModel):
    to: str
    cc: str | None = None
    subject: str = ""
    body: str = ""
    provider: str | None = "gmail"
    confirmation_required: bool = True


class MailSendResponse(BaseModel):
    status: str  # sent / blocked / confirmation_required
    draft_id: str | None = None
    message: str | None = None


class MailReplyRequest(BaseModel):
    body: str
    provider: str = "gmail"
    message_id: str


class MailReplyResponse(BaseModel):
    status: str  # sent / draft_created / confirmation_required
    draft_id: str | None = None
    message_id: str | None = None
