"""
Pydantic schemas for User-related responses.

These schemas control what user data is exposed through the API.
Notice that hashed_password is NEVER included in any response schema —
this is a critical security boundary.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    """Public representation of a User (never includes password hash)."""
    id: uuid.UUID
    email: EmailStr ## Recognize this is PII but is necessary for retrieval. Don't hash, just protect.
    user_type: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
