"""
Account model — a bank account owned by an AccountHolder.

Each account has:
  - A unique account number (randomly generated 10-digit string)
  - A type: "checking" or "savings"
  - A cached balance in integer cents (updated atomically with transactions)
  - A currency code (USD by default, ISO 4217)

Balance management:
  The `cached_balance_cents` column stores the current balance as an integer
  (in cents, e.g., $10.50 = 1050). This is updated atomically with every
  transaction in the same DB transaction — it's always consistent with the
  sum of all approved transactions.

  A CHECK constraint at the database level enforces that the balance can
  never go negative. This is a defense-in-depth measure: the application
  code also checks before debiting, but the DB constraint is the final
  safety net against bugs or race conditions.

Why integer cents?
  Floating-point numbers (float, Decimal) can introduce rounding errors
  in financial calculations. For example, 0.1 + 0.2 != 0.3 in IEEE 754
  floating point. By storing amounts as integer cents:
    - All arithmetic is exact (integers have no representation error)
    - $10.99 is stored as 1099 — no ambiguity
    - The frontend divides by 100 for display
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Account(Base):
    __tablename__ = "accounts"

    # Database-level constraint: balance can never be negative
    __table_args__ = (
        CheckConstraint(
            "cached_balance_cents >= 0",
            name="ck_accounts_non_negative_balance",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # Owner of this account
    account_holder_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("account_holders.id"),
        nullable=False,
        index=True,
    )

    # "checking" or "savings"
    account_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="checking",
    )

    # Unique 10-digit account number (generated at creation time)
    account_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
    )

    # Balance in cents — the source of truth for quick reads.
    # Updated atomically with each transaction.
    cached_balance_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # ISO 4217 currency code
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
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
    account_holder: Mapped["AccountHolder"] = relationship(
        back_populates="accounts",
    )
