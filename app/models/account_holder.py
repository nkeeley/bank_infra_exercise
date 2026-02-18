"""
AccountHolder model — the banking identity.

An AccountHolder is the "customer profile" in the banking system. It stores
personal information (name, phone) and owns zero or more bank accounts.

The relationship chain is:
    User (auth) --> AccountHolder (profile) --> Account(s) (banking)

Why is email denormalized from User?
  The AccountHolder stores its own copy of the email for convenience —
  it avoids a JOIN every time we need to display the holder's email in
  account-related queries. The email is set from the User at signup time
  and should be kept in sync if email changes are ever supported.

One-to-one with User:
  The user_id column has a UNIQUE constraint, ensuring each User maps to
  exactly one AccountHolder. This is enforced at both the database level
  (unique constraint) and the ORM level (uselist=False on the relationship).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AccountHolder(Base):
    __tablename__ = "account_holders"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign key to User — UNIQUE enforces the one-to-one relationship
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
    )

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Denormalized from User for query convenience (see module docstring)
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # --- Relationships ---
    user: Mapped["User"] = relationship(
        back_populates="account_holder",
    )

    # One AccountHolder can own many Accounts
    accounts: Mapped[list["Account"]] = relationship(
        back_populates="account_holder",
    )
