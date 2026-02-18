"""
Authentication router — signup and login endpoints.

These are the only public (unauthenticated) endpoints in the API.
Everything else requires a valid JWT token.

Endpoints:
  POST /auth/signup  — Register a new user and get a token
  POST /auth/login   — Authenticate and get a token

Security audit notes:
  - Plaintext passwords exist only in memory during request processing;
    they are hashed before any database operation and never logged.
  - JWT tokens appear only in response bodies, which are not logged by
    uvicorn (it logs method, path, and status code only).
  - SQLAlchemy's echo mode (DEBUG=True) logs SQL statements, but only
    the Argon2 hash is included in INSERT statements — never the plaintext.
  - No request body logging middleware is installed, so POST bodies
    containing passwords are not written to any log file.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import (
    UserSignupRequest,
    UserLoginRequest,
    TokenResponse,
    SignupResponse,
)
from app.services import auth_service

router = APIRouter()


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def signup(
    request: UserSignupRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new bank member.

    Creates a User (authentication identity) and an AccountHolder (banking
    profile) in a single atomic transaction. Returns a JWT token so the
    user is immediately logged in after signup.

    - **email**: Must be a valid email format and not already registered
    - **password**: Minimum 8 characters
    - **first_name** / **last_name**: Required, 1-100 characters
    - **phone**: Optional
    """
    user, token = await auth_service.signup(
        db=db,
        email=request.email,
        password=request.password,
        first_name=request.first_name,
        last_name=request.last_name,
        phone=request.phone,
    )

    return SignupResponse(
        user_id=user.id,
        email=user.email,
        user_type=user.user_type.value,
        token=token,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and get a token",
)
async def login(
    request: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with email and password.

    Returns a JWT bearer token that must be included in the Authorization
    header for all subsequent requests:

        Authorization: Bearer <token>

    The token expires after ACCESS_TOKEN_EXPIRE_MINUTES (default: 30).
    """
    user, token = await auth_service.login(
        db=db,
        email=request.email,
        password=request.password,
    )

    return TokenResponse(token=token)
