"""
Pydantic schemas for authentication endpoints (signup and login).

These schemas define the request/response contracts for the auth API.
Pydantic validates incoming data automatically — if a required field is
missing or the wrong type, FastAPI returns a 422 error before our code
even runs.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserSignupRequest(BaseModel):
    """Request body for POST /auth/signup."""
    email: EmailStr                                # Validates email format
    password: str = Field(min_length=8)            # Minimum 8 characters
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = None


class UserLoginRequest(BaseModel):
    """Request body for POST /auth/login."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Response body for successful login/signup — contains the JWT."""
    token: str
    token_type: str = "bearer"


class SignupResponse(BaseModel):
    """Response body for successful signup — user info + JWT."""
    user_id: uuid.UUID
    email: str
    user_type: str
    token: str
    token_type: str = "bearer"
