"""
Account service — business logic for bank account operations.

This module handles:
  - Account creation (with unique account number generation)
  - Account retrieval (single or list, scoped to an account holder)
  - Balance verification (cached vs. computed from transactions)

Ownership enforcement:
  All query functions accept an `account_holder_id` parameter. This is
  always the authenticated user's account holder ID, set by the dependency
  layer. There is no way for a regular member to query another user's
  accounts through this service — the scoping happens here, not in the
  router.

Admin access:
  Admin-specific functions (prefixed with `admin_`) do NOT scope by
  account_holder_id. They provide read-only access to:
    - All accounts (list and individual)
    - All balances
    - All transactions (implemented in transaction_service.py, Phase 4)
  The router layer enforces that only ADMIN users can call these endpoints.
"""

import uuid
import random
import string

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import AccountNotFoundError, UnauthorizedAccessError
from app.models.account import Account


def _generate_account_number() -> str:
    """
    Generate a random 10-digit account number.

    In a real bank, this would follow a specific format (routing number,
    check digit, etc.). For MVP, a random 10-digit string is sufficient
    and avoids sequential guessing.
    """
    return "".join(random.choices(string.digits, k=10))


async def create_account(
    db: AsyncSession,
    account_holder_id: uuid.UUID,
    account_type: str = "checking",
) -> Account:
    """
    Create a new bank account for an account holder.

    Generates a unique account number and initializes balance to 0 cents.

    Args:
        db: Database session.
        account_holder_id: The owner's account holder ID.
        account_type: "checking" or "savings".

    Returns:
        The newly created Account instance.
    """
    # Generate a unique account number (retry if collision, extremely unlikely)
    for _ in range(10):
        account_number = _generate_account_number()
        existing = await db.execute(
            select(Account).where(Account.account_number == account_number)
        )
        if existing.scalar_one_or_none() is None:
            break
    else:
        # This should effectively never happen with 10-digit random numbers
        raise RuntimeError("Failed to generate a unique account number")

    account = Account(
        account_holder_id=account_holder_id,
        account_type=account_type,
        account_number=account_number,
    )
    db.add(account)
    await db.flush()
    return account


async def get_accounts(
    db: AsyncSession,
    account_holder_id: uuid.UUID,
) -> list[Account]:
    """
    List all accounts belonging to a specific account holder.

    This is inherently scoped — only the owner's accounts are returned.
    """
    result = await db.execute(
        select(Account).where(Account.account_holder_id == account_holder_id)
    )
    return list(result.scalars().all())


async def get_account(
    db: AsyncSession,
    account_id: uuid.UUID,
    account_holder_id: uuid.UUID,
) -> Account:
    """
    Get a single account, verifying ownership.

    Args:
        db: Database session.
        account_id: The account to retrieve.
        account_holder_id: The authenticated user's account holder ID.

    Returns:
        The Account instance.

    Raises:
        AccountNotFoundError: If the account doesn't exist.
        UnauthorizedAccessError: If the account belongs to someone else.
    """
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()

    if account is None:
        raise AccountNotFoundError(account_id)

    if account.account_holder_id != account_holder_id:
        raise UnauthorizedAccessError("You do not have access to this account")

    return account


async def get_balance(
    db: AsyncSession,
    account_id: uuid.UUID,
    account_holder_id: uuid.UUID,
) -> dict:
    """
    Get the account balance — both cached and computed from transactions.

    The computed balance is calculated by summing all approved credits
    and subtracting all approved debits. If it doesn't match the cached
    balance, that signals a data integrity issue.

    Returns:
        Dict with cached_balance_cents, computed_balance_cents, match, currency.
    """
    account = await get_account(db, account_id, account_holder_id)
    computed_balance_cents = await _compute_balance_from_transactions(db, account_id)

    return {
        "account_id": account.id,
        "cached_balance_cents": account.cached_balance_cents,
        "computed_balance_cents": computed_balance_cents,
        "match": account.cached_balance_cents == computed_balance_cents,
        "currency": account.currency,
    }


async def _compute_balance_from_transactions(
    db: AsyncSession,
    account_id: uuid.UUID,
) -> int:
    """
    Compute the actual balance by summing all approved transactions.

    Credits (incoming) add to the balance, debits (outgoing) subtract.
    This is the integrity-check counterpart to cached_balance_cents.

    Returns 0 if the Transaction model hasn't been created yet.
    """
    try:
        from app.models.transaction import Transaction
    except ImportError:
        return 0

    # Sum approved credits to this account
    credit_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount_cents), 0))
        .where(Transaction.to_account_id == account_id)
        .where(Transaction.status == "approved")
        .where(Transaction.type == "credit")
    )
    total_credits = credit_result.scalar()

    # Sum approved debits from this account
    debit_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount_cents), 0))
        .where(Transaction.from_account_id == account_id)
        .where(Transaction.status == "approved")
        .where(Transaction.type == "debit")
    )
    total_debits = debit_result.scalar()

    return total_credits - total_debits


# ---------------------------------------------------------------------------
# Admin read-only functions
# ---------------------------------------------------------------------------

async def admin_get_all_accounts(db: AsyncSession) -> list[Account]:
    """
    [ADMIN ONLY] List all accounts across all account holders.

    Used for auditing and oversight. The router layer enforces that
    only ADMIN users can call this.
    """
    result = await db.execute(select(Account))
    return list(result.scalars().all())


async def admin_get_account(
    db: AsyncSession,
    account_id: uuid.UUID,
) -> Account:
    """
    [ADMIN ONLY] Get any account by ID without ownership check.

    Used for auditing. Returns the account regardless of who owns it.

    Raises:
        AccountNotFoundError: If the account doesn't exist.
    """
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()

    if account is None:
        raise AccountNotFoundError(account_id)

    return account


async def admin_get_balance(
    db: AsyncSession,
    account_id: uuid.UUID,
) -> dict:
    """
    [ADMIN ONLY] Get any account's balance without ownership check.
    """
    account = await admin_get_account(db, account_id)
    computed_balance_cents = await _compute_balance_from_transactions(db, account_id)

    return {
        "account_id": account.id,
        "cached_balance_cents": account.cached_balance_cents,
        "computed_balance_cents": computed_balance_cents,
        "match": account.cached_balance_cents == computed_balance_cents,
        "currency": account.currency,
    }
