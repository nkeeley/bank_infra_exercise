"""
Admin router — read-only endpoints for organization-wide visibility.

All endpoints require ADMIN role. Admins can view any account, balance,
or transaction for auditing purposes but CANNOT create accounts, initiate
transfers, or modify data.

Endpoints:
  GET  /admin/accounts                           — List ALL accounts
  GET  /admin/accounts/{account_id}              — Get any account's details
  GET  /admin/accounts/{account_id}/balance      — Get any account's balance
  GET  /admin/transactions                       — List ALL transactions org-wide
  GET  /admin/transactions/{transaction_id}      — Get any transaction by ID
  GET  /admin/accounts/{account_id}/transactions — List any account's transactions

By consolidating all admin routes in one router, we avoid route-ordering
conflicts that arise when multiple routers share a prefix and have
overlapping parameterized paths.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.models.user import User
from app.schemas.account import AccountResponse, BalanceResponse
from app.schemas.transaction import TransactionResponse
from app.services import account_service, transaction_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Account admin endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/accounts",
    response_model=list[AccountResponse],
    summary="[Admin] List all accounts",
)
async def admin_list_all_accounts(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    List all accounts across all account holders.

    This is a read-only auditing endpoint. Admins can see every account
    in the system but cannot modify any of them.
    """
    return await account_service.admin_get_all_accounts(db)


@router.get(
    "/accounts/{account_id}",
    response_model=AccountResponse,
    summary="[Admin] Get any account's details",
)
async def admin_get_account(
    account_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get any account's details without ownership check."""
    return await account_service.admin_get_account(db, account_id)


@router.get(
    "/accounts/{account_id}/balance",
    response_model=BalanceResponse,
    summary="[Admin] Get any account's balance",
)
async def admin_get_balance(
    account_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Get any account's balance without ownership check.

    Includes both cached and computed balance for integrity verification.
    """
    return await account_service.admin_get_balance(db, account_id)


# ---------------------------------------------------------------------------
# Transaction admin endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/transactions",
    response_model=list[TransactionResponse],
    summary="[Admin] List ALL transactions across the organization",
)
async def admin_list_all_transactions(
    status: str | None = Query(None, description="Filter by status"),
    type: str | None = Query(None, description="Filter by type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    List every transaction in the system.

    Provides a complete org-wide audit trail. Supports filtering by
    status (approved/declined/pending) and type (credit/debit), plus pagination.
    """
    return await transaction_service.admin_get_all_transactions(
        db=db,
        status_filter=status,
        type_filter=type,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/transactions/{transaction_id}",
    response_model=TransactionResponse,
    summary="[Admin] Get any transaction by ID",
)
async def admin_get_transaction(
    transaction_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get any single transaction by ID."""
    return await transaction_service.admin_get_transaction(
        db=db,
        transaction_id=transaction_id,
    )


@router.get(
    "/accounts/{account_id}/transactions",
    response_model=list[TransactionResponse],
    summary="[Admin] List any account's transactions",
)
async def admin_list_account_transactions(
    account_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all transactions for any specific account."""
    return await transaction_service.admin_get_account_transactions(
        db=db,
        account_id=account_id,
        limit=limit,
        offset=offset,
    )
