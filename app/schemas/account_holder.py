"""
Pydantic schemas for AccountHolder endpoints.

These define how account holder profile data flows in and out of the API.
The response schema uses from_attributes=True to auto-convert from
SQLAlchemy model instances.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AccountHolderResponse(BaseModel):
    """Public representation of an AccountHolder profile."""
    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    phone: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountHolderUpdateRequest(BaseModel):
    """Request body for PATCH /account-holders/me (all fields optional)."""
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    phone: str | None = None
