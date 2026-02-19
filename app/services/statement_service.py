"""
Statement service — monthly account statement generation.

Generates a statement for a specific account and month by:
  1. Querying all transactions in the date range
  2. Computing the opening balance (sum of all approved transactions before the month)
  3. Computing closing balance (opening + net of the month's transactions)
  4. Aggregating total credits and debits for the period

The opening balance is calculated from the transaction history rather than
stored separately. This ensures the statement is always consistent with
the actual transaction records — no stale cached values.

Enterprise note:
  In production, statements might be pre-generated and cached (or stored
  as PDFs) at month-end for performance. This on-demand approach is
  correct and sufficient for the MVP.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import AccountNotFoundError, UnauthorizedAccessError
from app.models.account import Account
from app.models.transaction import Transaction


async def generate_statement(
    db: AsyncSession,
    account_id: uuid.UUID,
    account_holder_id: uuid.UUID,
    year: int,
    month: int,
) -> dict:
    """
    Generate a monthly statement for an account.

    Args:
        db: Database session.
        account_id: The account to generate the statement for.
        account_holder_id: For ownership verification.
        year: Statement year (e.g., 2026).
        month: Statement month (1-12).

    Returns:
        Dictionary matching StatementResponse schema.

    Raises:
        AccountNotFoundError: If the account doesn't exist.
        UnauthorizedAccessError: If the account belongs to someone else.
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

    # Calculate date boundaries for the requested month
    month_start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        month_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        month_end = datetime(year, month + 1, 1, tzinfo=timezone.utc)

    # --- Opening balance: sum of all approved transactions BEFORE this month ---
    # Credits add to balance, debits subtract
    pre_month_credits = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount_cents), 0))
        .where(
            and_(
                Transaction.to_account_id == account_id,
                Transaction.status == "approved",
                Transaction.created_at < month_start,
            )
        )
    )
    pre_credits = pre_month_credits.scalar()

    pre_month_debits = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount_cents), 0))
        .where(
            and_(
                Transaction.from_account_id == account_id,
                Transaction.status == "approved",
                Transaction.created_at < month_start,
            )
        )
    )
    pre_debits = pre_month_debits.scalar()

    opening_balance = pre_credits - pre_debits

    # --- Transactions in the requested month ---
    month_txns_result = await db.execute(
        select(Transaction)
        .where(
            and_(
                or_(
                    Transaction.from_account_id == account_id,
                    Transaction.to_account_id == account_id,
                ),
                Transaction.created_at >= month_start,
                Transaction.created_at < month_end,
            )
        )
        .order_by(Transaction.created_at.asc())
    )
    transactions = list(month_txns_result.scalars().all())

    # --- Aggregate the month's approved transactions ---
    total_credits = sum(
        t.amount_cents for t in transactions
        if t.to_account_id == account_id and t.status == "approved"
    )
    total_debits = sum(
        t.amount_cents for t in transactions
        if t.from_account_id == account_id and t.status == "approved"
    )

    closing_balance = opening_balance + total_credits - total_debits

    return {
        "account_id": account_id,
        "year": year,
        "month": month,
        "opening_balance_cents": opening_balance,
        "closing_balance_cents": closing_balance,
        "total_credits_cents": total_credits,
        "total_debits_cents": total_debits,
        "transaction_count": len(transactions),
        "transactions": transactions,
    }
