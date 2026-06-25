"""OAuth token model — encrypted access and refresh tokens at rest."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base

if TYPE_CHECKING:
    from models.connected_account import ConnectedAccount


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    connected_account_id: Mapped[int] = mapped_column(
        ForeignKey("connected_accounts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    encrypted_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    connected_account: Mapped["ConnectedAccount"] = relationship(
        "ConnectedAccount",
        back_populates="oauth_token",
    )
