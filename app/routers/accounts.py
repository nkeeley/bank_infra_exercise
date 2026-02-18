"""
Accounts router — bank account management endpoints.

Two sets of endpoints are provided:

  Member endpoints (require JWT, scoped to the authenticated user):
    POST   /accounts                   — Create a new account
    GET    /accounts                   — List own accounts
    GET    /accounts/{account_id}      — Get own account details
    GET    /accounts/{account_id}/balance — Get own account balance

  Admin endpoints (require JWT + ADMIN role, read-only across all users):
    GET    /admin/accounts             — List ALL accounts
    GET    /admin/accounts/{account_id} — Get any account's details
    GET    /admin/accounts/{account_id}/balance — Get any account's balance

Admin endpoints are read-only by design. Admins can view any account,
balance, or transaction for auditing purposes, but CANNOT create accounts,
initiate transfers, or modify account data. This separation of concerns
prevents accidental or malicious financial operations by administrators.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_account_holder, require_admin
from app.models.account_holder import AccountHolder
from app.models.user import User
from app.schemas.account import AccountCreateRequest, AccountResponse, BalanceResponse
from app.services import account_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Member endpoints (scoped to authenticated user's accounts)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Admin endpoints (read-only access to all accounts)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/all",
    response_model=list[AccountResponse],
    summary="[Admin] List all accounts",
    tags=["Admin"],
)
async def admin_list_all_accounts(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    [ADMIN ONLY] List all accounts across all account holders.

    This is a read-only auditing endpoint. Admins can see every account
    in the system but cannot modify any of them.
    """
    return await account_service.admin_get_all_accounts(db)


@router.get(
    "/admin/{account_id}",
    response_model=AccountResponse,
    summary="[Admin] Get any account's details",
    tags=["Admin"],
)
async def admin_get_account(
    account_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    [ADMIN ONLY] Get any account's details without ownership check.
    """
    return await account_service.admin_get_account(db, account_id)


@router.get(
    "/admin/{account_id}/balance",
    response_model=BalanceResponse,
    summary="[Admin] Get any account's balance",
    tags=["Admin"],
)
async def admin_get_balance(
    account_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    [ADMIN ONLY] Get any account's balance without ownership check.

    Includes both cached and computed balance for integrity verification.
    """
    return await account_service.admin_get_balance(db, account_id)
