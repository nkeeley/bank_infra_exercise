"""
FastAPI dependencies for authentication and authorization.

Dependencies are reusable functions that FastAPI injects into route handlers.
They form a chain:

  get_current_user (JWT -> User)
      └── get_current_account_holder (User -> AccountHolder)

Every protected endpoint declares one of these as a parameter. FastAPI
automatically calls the dependency, and if it fails (e.g., invalid token),
the request is rejected before the route handler runs.

This is the authorization boundary — no user can access resources
without a valid JWT, and no account holder can be impersonated.
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.account_holder import AccountHolder
from app.security import decode_access_token


# OAuth2PasswordBearer tells FastAPI where to look for the token:
# the "Authorization: Bearer <token>" header. The tokenUrl points to
# the login endpoint (used by Swagger UI's "Authorize" button).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and validate the JWT token, then return the corresponding User.

    This dependency is the first line of defense: if the token is missing,
    expired, or tampered with, the request is rejected with 401.

    Args:
        token: JWT from the Authorization header (injected by OAuth2PasswordBearer).
        db: Database session (injected by get_db).

    Returns:
        The authenticated User instance.

    Raises:
        HTTPException 401: If the token is invalid or the user doesn't exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exception

    return user


async def get_current_account_holder(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AccountHolder:
    """
    Get the AccountHolder profile for the authenticated user.

    Chains on get_current_user — the user must be authenticated first.
    This is used by most banking endpoints (accounts, transactions, etc.)
    since they operate on the account holder level.

    Args:
        user: The authenticated User (injected by get_current_user).
        db: Database session.

    Returns:
        The AccountHolder instance associated with this user.

    Raises:
        HTTPException 404: If the user has no account holder profile
                           (should never happen in normal flow).
    """
    result = await db.execute(
        select(AccountHolder)
        .where(AccountHolder.user_id == user.id)
    )
    account_holder = result.scalar_one_or_none()

    if account_holder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account holder profile not found",
        )

    return account_holder
