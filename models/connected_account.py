"""Connected account model — links a user to an OAuth provider."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base

if TYPE_CHECKING:
    from models.oauth_token import OAuthToken
    from models.user import User


class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="connected")
    scopes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="connected_accounts")
    oauth_token: Mapped["OAuthToken | None"] = relationship(
        "OAuthToken",
        back_populates="connected_account",
        uselist=False,
        cascade="all, delete-orphan",
    )
