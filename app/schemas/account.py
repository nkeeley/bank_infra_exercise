"""
Pydantic schemas for Account endpoints.

These schemas define the API contract for account creation, retrieval,
and balance checking. All monetary amounts are expressed in integer cents.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AccountCreateRequest(BaseModel):
    """Request body for POST /accounts."""
    account_type: Literal["checking", "savings"] = Field(
        default="checking",
        description="Type of bank account to create",
    )


class AccountResponse(BaseModel):
    """Public representation of a bank account."""
    id: uuid.UUID
    account_holder_id: uuid.UUID
    account_type: str
    account_number: str
    cached_balance_cents: int
    currency: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class BalanceResponse(BaseModel):
    """
    Balance check response — includes both cached and computed values.

    The `match` field indicates whether the cached balance agrees with
    the balance computed by summing all approved transactions. A mismatch
    would indicate a data integrity issue.
    """
    account_id: uuid.UUID
    cached_balance_cents: int
    computed_balance_cents: int
    match: bool
    currency: str
