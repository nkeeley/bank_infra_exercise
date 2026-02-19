"""
Pydantic schemas for Card endpoints.

Card numbers and CVVs are NEVER returned in API responses. Only the
masked representation (last four digits) is exposed. This matches
how real banking APIs work — full card details are shown only once
at issuance time.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class CardResponse(BaseModel):
    """Public representation of a card (masked — no full number or CVV)."""
    id: uuid.UUID
    account_id: uuid.UUID
    card_number_last_four: str
    expiration_month: int
    expiration_year: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
