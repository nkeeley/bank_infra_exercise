"""
Card model — represents a debit/credit card linked to an account.

Each account can have at most ONE card (enforced by a unique constraint
on account_id). Card numbers and CVVs are encrypted at rest using Fernet
(AES-128-CBC + HMAC-SHA256). Only the last four digits are stored in
plaintext for display purposes.

Encryption strategy:
  - card_number_encrypted: Full 16-digit card number, Fernet-encrypted
  - cvv_encrypted: 3-digit CVV, Fernet-encrypted
  - card_number_last_four: Last 4 digits in plaintext (for "ending in ****")

Why encrypt and not hash?
  Unlike passwords (which only need verification), card numbers need to be
  recoverable for payment processing. Encryption (not hashing) allows
  decryption when needed, while protecting data at rest.

Enterprise note:
  In production, card data would be handled by a PCI DSS-compliant vault
  or tokenization service (e.g., Stripe, AWS CloudHSM). This implementation
  demonstrates the principle of encryption at rest.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, ForeignKey, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # One card per account — UNIQUE constraint prevents duplicates
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Full card number, Fernet-encrypted (AES-128-CBC + HMAC-SHA256)
    card_number_encrypted: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )

    # Last four digits in plaintext for display ("ending in 4242")
    card_number_last_four: Mapped[str] = mapped_column(
        String(4),
        nullable=False,
    )

    # Expiration date
    expiration_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    expiration_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # CVV, Fernet-encrypted
    cvv_encrypted: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
