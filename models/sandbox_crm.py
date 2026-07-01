"""Sandbox CRM models — holds mock CRM data for sandbox providers."""

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.database import Base


class SandboxAccount(Base):
    __tablename__ = "sandbox_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # hubspot, salesforce, zoho
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_name: Mapped[str] = mapped_column(String(255), default="Sales Rep")
    owner_email: Mapped[str] = mapped_column(String(255), default="rep@example.com")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contacts: Mapped[list["SandboxContact"]] = relationship("SandboxContact", back_populates="account", cascade="all, delete-orphan")
    deals: Mapped[list["SandboxDeal"]] = relationship("SandboxDeal", back_populates="account", cascade="all, delete-orphan")


class SandboxContact(Base):
    __tablename__ = "sandbox_contacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("sandbox_accounts.id", ondelete="SET NULL"), nullable=True)
    owner_name: Mapped[str] = mapped_column(String(255), default="Sales Rep")
    owner_email: Mapped[str] = mapped_column(String(255), default="rep@example.com")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped["SandboxAccount | None"] = relationship("SandboxAccount", back_populates="contacts")


class SandboxDeal(Base):
    __tablename__ = "sandbox_deals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    close_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("sandbox_accounts.id", ondelete="SET NULL"), nullable=True)
    owner_name: Mapped[str] = mapped_column(String(255), default="Sales Rep")
    owner_email: Mapped[str] = mapped_column(String(255), default="rep@example.com")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped["SandboxAccount | None"] = relationship("SandboxAccount", back_populates="deals")


class SandboxNote(Base):
    __tablename__ = "sandbox_notes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # contact, account, deal
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)   # the CRM ID of target entity
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SandboxTask(Base):
    __tablename__ = "sandbox_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # contact, account, deal
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)   # the CRM ID of target entity
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
