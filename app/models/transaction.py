"""
Transaction model — records every financial event in the system.

Every movement of money creates a Transaction record. The core design
follows double-entry bookkeeping principles:

  - A deposit creates one CREDIT transaction (money into an account)
  - A withdrawal creates one DEBIT transaction (money out of an account)
  - A transfer creates TWO transactions: a DEBIT from the source and a
    CREDIT to the destination, linked by a shared `transfer_pair_id`

Key fields:
  - type: "credit" or "debit" — the direction of money flow
  - amount_cents: Always positive (the direction is implied by the type)
  - from_account_id: The source account (NULL for deposits from external)
  - to_account_id: The destination account (NULL for withdrawals/purchases)
  - status: "pending", "approved", or "declined"
  - transfer_pair_id: Links the two legs of a transfer (NULL for non-transfers)
  - card_id: The debit card used for the purchase (NULL for non-card transactions)

Status field:
  For MVP, transactions are immediately "approved" or "declined" (synchronous).
  The "pending" status is included for enterprise readiness — in a real bank,
  external transfers might be held for review, fraud checks, or settlement.

Why amount_cents is always positive:
  Storing a positive amount with a separate type field (credit/debit) is
  clearer than using signed integers. You never wonder "does negative mean
  credit or debit?" — the type field makes the direction explicit.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    __table_args__ = (
        # Amount must always be positive — direction is indicated by type
        CheckConstraint("amount_cents > 0", name="ck_transactions_positive_amount"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # "credit" (money in) or "debit" (money out)
    type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    # Amount in cents — always positive
    amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Source account (NULL for external deposits)
    from_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id"),
        nullable=True,
        index=True,
    )

    # Destination account (NULL for withdrawals/purchases)
    to_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id"),
        nullable=True,
        index=True,
    )

    # "pending", "approved", or "declined"
    status: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="pending",
    )

    # Optional description/memo
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Links two legs of a transfer — both the debit and credit transactions
    # in a transfer share the same transfer_pair_id UUID
    transfer_pair_id: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True,
        index=True,
    )

    # The debit card used for this purchase (NULL for non-card transactions).
    # Only set on debit transactions — the card must belong to the same account.
    card_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cards.id"),
        nullable=True,
        index=True,
    )

    # Transaction timestamp — indexed for efficient date-range queries (statements)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
