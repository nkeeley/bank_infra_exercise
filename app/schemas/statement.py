"""
Pydantic schemas for monthly statement endpoints.

A statement is produced per account, aggregated monthly. The response
structure puts aggregate data at the top (opening/closing balance, totals)
followed by the full list of transactions for that month.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.transaction import TransactionResponse


class StatementResponse(BaseModel):
    """Monthly account statement.

    Aggregates appear first — these are the "header" a user sees at the
    top of their statement. The full transaction list follows, ordered
    chronologically so the user can scroll through every transaction.
    """
    # --- Statement metadata ---
    account_id: uuid.UUID
    year: int
    month: int

    # --- Aggregates (top of statement) ---
    opening_balance_cents: int
    closing_balance_cents: int
    total_credits_cents: int
    total_debits_cents: int
    transaction_count: int

    # --- Full transaction list (scrollable) ---
    transactions: list[TransactionResponse]
