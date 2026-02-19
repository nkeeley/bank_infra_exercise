"""
Card service — card issuance and retrieval with encryption at rest.

Each account can have at most one card. When a card is issued:
  1. A 16-digit card number is randomly generated
  2. A 3-digit CVV is randomly generated
  3. Expiration is set to 3 years from now
  4. The card number and CVV are encrypted with Fernet before storage
  5. Only the last four digits are stored in plaintext (for display)

The full card number and CVV are encrypted using Fernet (AES-128-CBC +
HMAC-SHA256), meaning they cannot be read from the database without the
encryption key. This protects against database breaches.
"""

import random
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import AccountNotFoundError, DuplicateCardError, UnauthorizedAccessError
from app.models.account import Account
from app.models.card import Card
from app.security import encrypt_value


def _generate_card_number() -> str:
    """Generate a random 16-digit card number.

    In production, card numbers follow the Luhn algorithm and are assigned
    by the card network (Visa, Mastercard, etc.). For this MVP, we use a
    random 16-digit number starting with "4" (Visa-like).
    """
    return "4" + "".join([str(random.randint(0, 9)) for _ in range(15)])


def _generate_cvv() -> str:
    """Generate a random 3-digit CVV."""
    return "".join([str(random.randint(0, 9)) for _ in range(3)])


async def issue_card(
    db: AsyncSession,
    account_id: uuid.UUID,
    account_holder_id: uuid.UUID,
) -> Card:
    """
    Issue a new card for an account.

    Verifies account ownership, checks that no card already exists,
    generates card details, encrypts sensitive fields, and stores the card.

    Args:
        db: Database session.
        account_id: The account to issue a card for.
        account_holder_id: For ownership verification.

    Returns:
        The created Card instance.

    Raises:
        AccountNotFoundError: If the account doesn't exist.
        UnauthorizedAccessError: If the account belongs to someone else.
        DuplicateCardError: If the account already has a card.
    """
    # Verify ownership
    result = await db.execute(
        select(Account).where(Account.id == account_id)
    )
    account = result.scalar_one_or_none()

    if account is None:
        raise AccountNotFoundError(account_id)
    if account.account_holder_id != account_holder_id:
        raise UnauthorizedAccessError("You do not have access to this account")

    # Check for existing card
    existing = await db.execute(
        select(Card).where(Card.account_id == account_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise DuplicateCardError(account_id)

    # Generate card details
    card_number = _generate_card_number()
    cvv = _generate_cvv()
    now = datetime.now(timezone.utc)

    card = Card(
        account_id=account_id,
        card_number_encrypted=encrypt_value(card_number),
        card_number_last_four=card_number[-4:],
        expiration_month=now.month,
        expiration_year=now.year + 3,  # 3-year expiration
        cvv_encrypted=encrypt_value(cvv),
    )

    db.add(card)
    await db.flush()
    return card


async def get_card(
    db: AsyncSession,
    account_id: uuid.UUID,
    account_holder_id: uuid.UUID,
) -> Card:
    """
    Get the card for an account (masked — no full number or CVV returned).

    Args:
        db: Database session.
        account_id: The account to get the card for.
        account_holder_id: For ownership verification.

    Returns:
        The Card instance (serialized via CardResponse, which excludes
        encrypted fields).

    Raises:
        AccountNotFoundError: If the account doesn't exist.
        UnauthorizedAccessError: If the account belongs to someone else.
        HTTPException 404: If no card exists for this account.
    """
    # Verify ownership
    result = await db.execute(
        select(Account).where(Account.id == account_id)
    )
    account = result.scalar_one_or_none()

    if account is None:
        raise AccountNotFoundError(account_id)
    if account.account_holder_id != account_holder_id:
        raise UnauthorizedAccessError("You do not have access to this account")

    # Get the card
    card_result = await db.execute(
        select(Card).where(Card.account_id == account_id)
    )
    card = card_result.scalar_one_or_none()

    if card is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No card found for this account",
        )

    return card
