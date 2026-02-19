"""
Transaction service — the core financial business logic.

THIS IS THE MOST CRITICAL FILE IN THE PROJECT. It handles:
  - Creating individual transactions (credits and debits)
  - Executing atomic transfers between accounts
  - Balance enforcement (no negative balances)
  - Declined transaction audit trail

Atomicity:
  Every balance change and its corresponding transaction record are
  created inside the SAME database transaction. If either fails, both
  are rolled back. This guarantees that the cached_balance_cents column
  on the Account always matches the sum of approved transactions.

  For transfers, both the debit (from source) and credit (to destination)
  happen in a single database transaction with begin_nested() (SAVEPOINT).

Deadlock prevention:
  When a transfer involves two accounts, we always lock them in a
  consistent order (sorted by UUID). This prevents the classic deadlock
  scenario where:
    - Transfer A->B locks A, then tries to lock B
    - Transfer B->A locks B, then tries to lock A
  By always locking the lower UUID first, we guarantee a consistent
  lock ordering.

SQLite note:
  SQLite doesn't support SELECT ... FOR UPDATE (row-level locking).
  The with_for_update() calls are no-ops on SQLite but position the
  code correctly for PostgreSQL migration. SQLite's serialized
  transaction mode provides sufficient isolation for single-process use.

Admin read-only functions:
  Functions prefixed with `admin_` provide read access to all transactions
  without ownership scoping. These are called from admin-only endpoints.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import AccountNotFoundError, InsufficientFundsError, UnauthorizedAccessError
from app.models.account import Account
from app.models.card import Card
from app.models.transaction import Transaction


async def create_transaction(
    db: AsyncSession,
    account_id: uuid.UUID,
    account_holder_id: uuid.UUID,
    txn_type: str,
    amount_cents: int,
    description: str | None = None,
    card_id: uuid.UUID | None = None,
) -> Transaction:
    """
    Create a single credit or debit transaction.

    For CREDITS (deposits):
      - Adds amount to the account's cached_balance_cents
      - Creates an approved transaction with to_account_id set
      - card_id is not allowed (deposits don't use cards)

    For DEBITS (purchases/withdrawals):
      - If card_id is provided, validates the card belongs to this account
        and is active (debit card purchase)
      - Checks if the account has sufficient balance
      - If insufficient: creates a DECLINED transaction for the audit trail
        and raises InsufficientFundsError
      - If sufficient: deducts from cached_balance_cents and creates an
        approved transaction with from_account_id set

    Args:
        db: Database session.
        account_id: The account to credit/debit.
        account_holder_id: The authenticated user's account holder ID
                           (for ownership verification).
        txn_type: "credit" or "debit".
        amount_cents: Positive integer amount in cents.
        description: Optional memo/narrative.
        card_id: Optional debit card used for this purchase.

    Returns:
        The created Transaction instance.

    Raises:
        AccountNotFoundError: If the account doesn't exist.
        UnauthorizedAccessError: If the account belongs to someone else.
        InsufficientFundsError: If a debit would cause a negative balance.
        HTTPException 400: If card_id is provided on a credit transaction,
                           or the card doesn't belong to this account.
    """
    # Verify ownership and lock the account row
    result = await db.execute(
        select(Account)
        .where(Account.id == account_id)
        .with_for_update()  # No-op on SQLite, locks row on PostgreSQL
    )
    account = result.scalar_one_or_none()

    if account is None:
        raise AccountNotFoundError(account_id)

    if account.account_holder_id != account_holder_id:
        raise UnauthorizedAccessError("You do not have access to this account")

    # Validate card usage
    if card_id is not None:
        from fastapi import HTTPException, status as http_status

        if txn_type == "credit":
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Cards cannot be used for deposit (credit) transactions",
            )

        card_result = await db.execute(
            select(Card).where(Card.id == card_id)
        )
        card = card_result.scalar_one_or_none()

        if card is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Card not found",
            )
        if card.account_id != account_id:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Card does not belong to this account",
            )
        if not card.is_active:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Card is not active",
            )

    if txn_type == "debit":
        if account.cached_balance_cents < amount_cents:
            # Create a declined transaction for the audit trail
            declined_txn = Transaction(
                type="debit",
                amount_cents=amount_cents,
                from_account_id=account_id,
                status="declined",
                description=description,
                card_id=card_id,
            )
            db.add(declined_txn)
            await db.flush()

            raise InsufficientFundsError(
                account_id=account_id,
                requested_cents=amount_cents,
                available_cents=account.cached_balance_cents,
            )

        # Debit: subtract from balance
        account.cached_balance_cents -= amount_cents
        txn = Transaction(
            type="debit",
            amount_cents=amount_cents,
            from_account_id=account_id,
            status="approved",
            description=description,
            card_id=card_id,
        )
    else:
        # Credit: add to balance
        account.cached_balance_cents += amount_cents
        txn = Transaction(
            type="credit",
            amount_cents=amount_cents,
            to_account_id=account_id,
            status="approved",
            description=description,
        )

    db.add(txn)
    await db.flush()
    return txn


async def create_transfer(
    db: AsyncSession,
    from_account_id: uuid.UUID,
    to_account_id: uuid.UUID,
    account_holder_id: uuid.UUID,
    amount_cents: int,
    description: str | None = None,
) -> tuple[Transaction, Transaction, uuid.UUID]:
    """
    Execute an atomic transfer between two accounts.

    This creates TWO transactions (debit + credit) linked by a shared
    transfer_pair_id. Both the balance updates and transaction inserts
    happen in a single database transaction.

    DEADLOCK PREVENTION: Accounts are locked in sorted UUID order.
    This ensures consistent lock ordering even when concurrent transfers
    happen between the same pair of accounts in opposite directions.

    Args:
        db: Database session.
        from_account_id: Source account (must belong to the authenticated user).
        to_account_id: Destination account (can belong to anyone).
        account_holder_id: The authenticated user's account holder ID.
        amount_cents: Positive integer amount in cents.
        description: Optional memo/narrative.

    Returns:
        Tuple of (debit_transaction, credit_transaction, transfer_pair_id).

    Raises:
        AccountNotFoundError: If either account doesn't exist.
        UnauthorizedAccessError: If the source account doesn't belong to the user.
        InsufficientFundsError: If the source account has insufficient balance.
    """
    transfer_pair_id = uuid.uuid4()

    # Lock accounts in consistent order (sorted by UUID) to prevent deadlocks
    first_id, second_id = sorted([from_account_id, to_account_id])

    first_result = await db.execute(
        select(Account).where(Account.id == first_id).with_for_update()
    )
    first_account = first_result.scalar_one_or_none()

    second_result = await db.execute(
        select(Account).where(Account.id == second_id).with_for_update()
    )
    second_account = second_result.scalar_one_or_none()

    # Verify both accounts exist
    if first_account is None:
        raise AccountNotFoundError(first_id)
    if second_account is None:
        raise AccountNotFoundError(second_id)

    # Map back to source/destination
    source = first_account if first_account.id == from_account_id else second_account
    dest = second_account if second_account.id == to_account_id else first_account

    # Verify the authenticated user owns the SOURCE account
    if source.account_holder_id != account_holder_id:
        raise UnauthorizedAccessError("You do not have access to the source account")

    # Check balance on source
    if source.cached_balance_cents < amount_cents:
        # Create declined debit for audit trail (scoped to source account only)
        declined_txn = Transaction(
            type="debit",
            amount_cents=amount_cents,
            from_account_id=from_account_id,
            to_account_id=None,
            status="declined",
            description=description,
            transfer_pair_id=transfer_pair_id,
        )
        db.add(declined_txn)
        await db.flush()

        raise InsufficientFundsError(
            account_id=from_account_id,
            requested_cents=amount_cents,
            available_cents=source.cached_balance_cents,
        )

    # Update balances atomically
    source.cached_balance_cents -= amount_cents
    dest.cached_balance_cents += amount_cents

    # Create paired transactions — each leg is scoped to its own account.
    # The debit only sets from_account_id (source), the credit only sets
    # to_account_id (destination). The shared transfer_pair_id links them
    # for auditing and reconciliation.
    debit_txn = Transaction(
        type="debit",
        amount_cents=amount_cents,
        from_account_id=from_account_id,
        to_account_id=None,
        status="approved",
        description=description,
        transfer_pair_id=transfer_pair_id,
    )
    credit_txn = Transaction(
        type="credit",
        amount_cents=amount_cents,
        from_account_id=None,
        to_account_id=to_account_id,
        status="approved",
        description=description,
        transfer_pair_id=transfer_pair_id,
    )
    db.add_all([debit_txn, credit_txn])
    await db.flush()

    return debit_txn, credit_txn, transfer_pair_id


async def get_transactions(
    db: AsyncSession,
    account_id: uuid.UUID,
    account_holder_id: uuid.UUID,
    status_filter: str | None = None,
    type_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Transaction]:
    """
    List transactions for an account, with optional filters.

    Only returns transactions where the account is either the source
    (from_account_id) or destination (to_account_id).

    Args:
        db: Database session.
        account_id: The account to query transactions for.
        account_holder_id: For ownership verification.
        status_filter: Optional filter by status ("approved", "declined", "pending").
        type_filter: Optional filter by type ("credit", "debit").
        limit: Max number of results (default 50).
        offset: Number of results to skip (for pagination).

    Returns:
        List of Transaction instances, ordered by created_at descending.
    """
    # Verify ownership first
    from app.services.account_service import get_account
    await get_account(db, account_id, account_holder_id)

    query = (
        select(Transaction)
        .where(
            (Transaction.from_account_id == account_id)
            | (Transaction.to_account_id == account_id)
        )
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    if status_filter:
        query = query.where(Transaction.status == status_filter)
    if type_filter:
        query = query.where(Transaction.type == type_filter)

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_transaction(
    db: AsyncSession,
    account_id: uuid.UUID,
    transaction_id: uuid.UUID,
    account_holder_id: uuid.UUID,
) -> Transaction:
    """
    Get a single transaction by ID, verifying account ownership.

    Raises:
        AccountNotFoundError: If the account doesn't exist.
        UnauthorizedAccessError: If the account belongs to someone else.
        HTTPException 404: If the transaction doesn't exist or doesn't
                           belong to this account.
    """
    from app.services.account_service import get_account
    await get_account(db, account_id, account_holder_id)

    result = await db.execute(
        select(Transaction)
        .where(Transaction.id == transaction_id)
        .where(
            (Transaction.from_account_id == account_id)
            | (Transaction.to_account_id == account_id)
        )
    )
    txn = result.scalar_one_or_none()

    if txn is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    return txn


# ---------------------------------------------------------------------------
# Admin read-only functions
# ---------------------------------------------------------------------------

async def admin_get_all_transactions(
    db: AsyncSession,
    status_filter: str | None = None,
    type_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Transaction]:
    """
    [ADMIN ONLY] List ALL transactions across the entire organization.

    This provides a complete audit trail — admins can see every financial
    event in the system. Supports filtering by status and type, plus pagination.
    """
    query = (
        select(Transaction)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    if status_filter:
        query = query.where(Transaction.status == status_filter)
    if type_filter:
        query = query.where(Transaction.type == type_filter)

    result = await db.execute(query)
    return list(result.scalars().all())


async def admin_get_account_transactions(
    db: AsyncSession,
    account_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[Transaction]:
    """
    [ADMIN ONLY] List all transactions for any account without ownership check.
    """
    # Verify the account exists
    account_result = await db.execute(
        select(Account).where(Account.id == account_id)
    )
    if account_result.scalar_one_or_none() is None:
        raise AccountNotFoundError(account_id)

    result = await db.execute(
        select(Transaction)
        .where(
            (Transaction.from_account_id == account_id)
            | (Transaction.to_account_id == account_id)
        )
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def admin_get_transaction(
    db: AsyncSession,
    transaction_id: uuid.UUID,
) -> Transaction:
    """
    [ADMIN ONLY] Get any single transaction by ID without ownership check.
    """
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    txn = result.scalar_one_or_none()

    if txn is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    return txn
