"""
Accounts router — bank account management endpoints for members.

Member endpoints (require JWT, scoped to the authenticated user):
  POST   /accounts                   — Create a new account
  GET    /accounts                   — List own accounts
  GET    /accounts/{account_id}      — Get own account details
  GET    /accounts/{account_id}/balance — Get own account balance

Admin endpoints are in the dedicated admin router (app/routers/admin.py)
to avoid route-ordering conflicts with parameterized paths.
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_account_holder
from app.models.account_holder import AccountHolder
from app.schemas.account import AccountCreateRequest, AccountLookupResponse, AccountResponse, BalanceResponse
from app.services import account_service

router = APIRouter()


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new bank account",
)
async def create_account(
    request: AccountCreateRequest,
    account_holder: AccountHolder = Depends(get_current_account_holder),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new checking or savings account.

    The account is created with a zero balance and a randomly generated
    10-digit account number. The authenticated user automatically becomes
    the owner.
    """
    account = await account_service.create_account(
        db=db,
        account_holder_id=account_holder.id,
        account_type=request.account_type,
    )
    return account


@router.get(
    "",
    response_model=list[AccountResponse],
    summary="List your accounts",
)
async def list_accounts(
    account_holder: AccountHolder = Depends(get_current_account_holder),
    db: AsyncSession = Depends(get_db),
):
    """
    List all bank accounts owned by the authenticated user.

    Only returns accounts belonging to the current user — there is no
    way to see other users' accounts through this endpoint.
    """
    return await account_service.get_accounts(db, account_holder.id)


@router.get(
    "/lookup",
    response_model=AccountLookupResponse,
    summary="Look up an account by account number",
)
async def lookup_account(
    account_number: str = Query(..., min_length=1, description="The 10-digit account number"),
    account_holder: AccountHolder = Depends(get_current_account_holder),
    db: AsyncSession = Depends(get_db),
):
    """
    Look up an account by its account number for transfers.

    Returns minimal info (ID, type, number) — no balance or owner details.
    Any authenticated member can look up any account number, which is how
    real banks work: you need someone's account number to send them money.
    """
    return await account_service.lookup_by_account_number(db, account_number)


@router.get(
    "/{account_id}",
    response_model=AccountResponse,
    summary="Get account details",
)
async def get_account(
    account_id: uuid.UUID,
    account_holder: AccountHolder = Depends(get_current_account_holder),
    db: AsyncSession = Depends(get_db),
):
    """
    Get details for a specific account.

    Returns 403 if the account belongs to a different user, or 404 if
    the account doesn't exist.
    """
    return await account_service.get_account(db, account_id, account_holder.id)


@router.get(
    "/{account_id}/balance",
    response_model=BalanceResponse,
    summary="Check account balance",
)
async def get_balance(
    account_id: uuid.UUID,
    account_holder: AccountHolder = Depends(get_current_account_holder),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the account balance — both cached and computed from transactions.

    The response includes a `match` boolean indicating whether the cached
    balance agrees with the sum of all transactions. A mismatch would
    indicate a data integrity issue that needs investigation.
    """
    return await account_service.get_balance(db, account_id, account_holder.id)
