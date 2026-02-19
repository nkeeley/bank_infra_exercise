"""
Pydantic schemas for Transaction and Transfer endpoints.

All monetary amounts are in integer cents (e.g., $10.50 = 1050).
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class TransactionCreateRequest(BaseModel):
    """Request body for POST /accounts/{id}/transactions."""
    type: Literal["credit", "debit"]
    amount_cents: int = Field(gt=0, description="Amount in cents (must be positive)")
    description: str | None = None
    card_id: uuid.UUID | None = Field(
        None, description="Optional debit card ID used for this purchase (debit only)"
    )


class TransactionResponse(BaseModel):
    """Public representation of a transaction."""
    id: uuid.UUID
    type: str
    amount_cents: int
    from_account_id: uuid.UUID | None
    to_account_id: uuid.UUID | None
    status: str
    description: str | None
    transfer_pair_id: uuid.UUID | None
    card_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TransferRequest(BaseModel):
    """Request body for POST /transfers."""
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount_cents: int = Field(gt=0, description="Amount in cents (must be positive)")
    description: str | None = None

    @model_validator(mode="after")
    def accounts_must_differ(self):
        """Cannot transfer money to the same account."""
        if self.from_account_id == self.to_account_id:
            raise ValueError("Cannot transfer to the same account")
        return self


class TransferResponse(BaseModel):
    """Response body for a successful transfer."""
    transfer_pair_id: uuid.UUID
    debit_transaction: TransactionResponse
    credit_transaction: TransactionResponse
    amount_cents: int
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
