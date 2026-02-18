"""
Account Holders router — profile management endpoints.

These endpoints let authenticated users view and update their banking
profile (AccountHolder). Every request requires a valid JWT token.

Endpoints:
  GET   /account-holders/me  — Get current user's profile
  PATCH /account-holders/me  — Update profile fields
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_account_holder
from app.models.account_holder import AccountHolder
from app.schemas.account_holder import AccountHolderResponse, AccountHolderUpdateRequest

router = APIRouter()


@router.get(
    "/me",
    response_model=AccountHolderResponse,
    summary="Get current user's profile",
)
async def get_my_profile(
    account_holder: AccountHolder = Depends(get_current_account_holder),
):
    """
    Return the authenticated user's account holder profile.

    The JWT token identifies the user, and the dependency chain resolves
    the associated AccountHolder automatically.
    """
    return account_holder


@router.patch(
    "/me",
    response_model=AccountHolderResponse,
    summary="Update profile fields",
)
async def update_my_profile(
    updates: AccountHolderUpdateRequest,
    account_holder: AccountHolder = Depends(get_current_account_holder),
    db: AsyncSession = Depends(get_db),
):
    """
    Update the authenticated user's profile.

    Only provided (non-None) fields are updated — omitted fields remain
    unchanged. This is the PATCH semantic: partial updates.
    """
    # model_dump(exclude_unset=True) only includes fields the client explicitly sent
    update_data = updates.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(account_holder, field, value)

    await db.flush()
    return account_holder
