"""
Transactions router — create and list transactions for an account.

Member endpoints (scoped to authenticated user's accounts):
  POST /accounts/{account_id}/transactions       — Create a credit or debit
  GET  /accounts/{account_id}/transactions        — List transactions (with filters)
  GET  /accounts/{account_id}/transactions/{id}   — Get a single transaction

Admin endpoints are in the dedicated admin router (app/routers/admin.py)
to avoid route-ordering conflicts with parameterized paths.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_account_holder
from app.models.account_holder import AccountHolder
from app.schemas.transaction import (
    TransactionCreateRequest,
    TransactionResponse,
)
from app.services import transaction_service

router = APIRouter()


@router.post(
    "/{account_id}/transactions",
    response_model=TransactionResponse,
    status_code=201,
    summary="Create a transaction (credit or debit)",
)
async def create_transaction(
    account_id: uuid.UUID,
    request: TransactionCreateRequest,
    account_holder: AccountHolder = Depends(get_current_account_holder),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a credit (deposit) or debit (purchase/withdrawal) transaction.

    - **credit**: Adds money to the account (e.g., paycheck deposit)
    - **debit**: Removes money from the account (e.g., purchase)

    Debits are rejected if the account has insufficient balance. A declined
    transaction is still recorded for audit purposes.

    All amounts are in **integer cents** (e.g., $10.50 = 1050).
    """
    txn = await transaction_service.create_transaction(
        db=db,
        account_id=account_id,
        account_holder_id=account_holder.id,
        txn_type=request.type,
        amount_cents=request.amount_cents,
        description=request.description,
    )
    return txn


@router.get(
    "/{account_id}/transactions",
    response_model=list[TransactionResponse],
    summary="List transactions for an account",
)
async def list_transactions(
    account_id: uuid.UUID,
    status: str | None = Query(None, description="Filter by status: approved, declined, pending"),
    type: str | None = Query(None, description="Filter by type: credit, debit"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    account_holder: AccountHolder = Depends(get_current_account_holder),
    db: AsyncSession = Depends(get_db),
):
    """
    List transactions for a specific account, newest first.

    Supports optional filtering by status and type, plus pagination.
    """
    return await transaction_service.get_transactions(
        db=db,
        account_id=account_id,
        account_holder_id=account_holder.id,
        status_filter=status,
        type_filter=type,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{account_id}/transactions/{transaction_id}",
    response_model=TransactionResponse,
    summary="Get a single transaction",
)
async def get_transaction(
    account_id: uuid.UUID,
    transaction_id: uuid.UUID,
    account_holder: AccountHolder = Depends(get_current_account_holder),
    db: AsyncSession = Depends(get_db),
):
    """Get details for a specific transaction."""
    return await transaction_service.get_transaction(
        db=db,
        account_id=account_id,
        transaction_id=transaction_id,
        account_holder_id=account_holder.id,
    )
