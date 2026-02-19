"""
Cards router — card issuance and retrieval for accounts.

Endpoints:
  POST /accounts/{account_id}/card — Issue a new card for an account
  GET  /accounts/{account_id}/card — Get the card (masked, no full number or CVV)

Each account can have at most one card. Card numbers and CVVs are
encrypted at rest and never returned in API responses — only the
last four digits are exposed for display.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_account_holder
from app.models.account_holder import AccountHolder
from app.schemas.card import CardResponse
from app.services import card_service

router = APIRouter()


@router.post(
    "/{account_id}/card",
    response_model=CardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a card for an account",
)
async def issue_card(
    account_id: uuid.UUID,
    account_holder: AccountHolder = Depends(get_current_account_holder),
    db: AsyncSession = Depends(get_db),
):
    """
    Issue a new debit card for the specified account.

    - Each account can have at most ONE card
    - The card number and CVV are encrypted at rest
    - Only the last four digits are returned for display
    - Expiration is set to 3 years from issuance
    """
    card = await card_service.issue_card(
        db=db,
        account_id=account_id,
        account_holder_id=account_holder.id,
    )
    return card


@router.get(
    "/{account_id}/card",
    response_model=CardResponse,
    summary="Get card details (masked)",
)
async def get_card(
    account_id: uuid.UUID,
    account_holder: AccountHolder = Depends(get_current_account_holder),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the card for an account.

    Returns masked card details — the full card number and CVV are
    never exposed through the API. Only the last four digits are shown.
    """
    return await card_service.get_card(
        db=db,
        account_id=account_id,
        account_holder_id=account_holder.id,
    )
