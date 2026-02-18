"""
Authentication service — signup and login business logic.

This module contains the core auth logic, separated from HTTP concerns.
The router calls these functions and translates the results into HTTP
responses. This separation means the business logic can be tested
without spinning up a web server.

Signup flow:
  1. Check if email is already registered
  2. Hash the password with Argon2id
  3. Create User + AccountHolder in a single database transaction
  4. Return a JWT token so the user is immediately logged in

Login flow:
  1. Look up user by email
  2. Verify password against stored hash
  3. Return a JWT token

Security notes:
  - Passwords are hashed before storage (never stored in plaintext)
  - Login returns the same error for "wrong password" and "email not found"
    to prevent user enumeration attacks
  - JWT tokens are stateless — no server-side session storage needed
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DuplicateEmailError, InvalidCredentialsError
from app.models.user import User, UserType
from app.models.account_holder import AccountHolder
from app.security import hash_password, verify_password, create_access_token


async def signup(
    db: AsyncSession,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    phone: str | None = None,
) -> tuple[User, str]:
    """
    Register a new user and create their account holder profile.

    This creates both records in a single transaction — if either fails,
    neither is persisted (atomicity).

    Args:
        db: Database session.
        email: User's email (must be unique).
        password: Plaintext password (will be hashed before storage).
        first_name: Account holder's first name.
        last_name: Account holder's last name.
        phone: Optional phone number.

    Returns:
        Tuple of (User instance, JWT token string).

    Raises:
        DuplicateEmailError: If the email is already registered.
    """
    # Check for existing email
    result = await db.execute(select(User).where(User.email == email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise DuplicateEmailError(email)

    # Create the User (auth identity)
    user = User(
        email=email,
        hashed_password=hash_password(password),
        user_type=UserType.MEMBER,
    )
    db.add(user)
    # Flush to get the user.id assigned (needed for the FK below)
    await db.flush()

    # Create the AccountHolder (banking profile)
    account_holder = AccountHolder(
        user_id=user.id,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
    )
    db.add(account_holder)
    await db.flush()

    # Generate JWT token — "sub" (subject) is the standard claim for user identity
    token = create_access_token(data={"sub": str(user.id)})

    return user, token


async def login(
    db: AsyncSession,
    email: str,
    password: str,
) -> tuple[User, str]:
    """
    Authenticate a user and return a JWT token.

    Security: Returns the same error for both "wrong password" and
    "email not found" to prevent attackers from enumerating valid emails.

    Args:
        db: Database session.
        email: User's email.
        password: Plaintext password to verify.

    Returns:
        Tuple of (User instance, JWT token string).

    Raises:
        InvalidCredentialsError: If email doesn't exist or password is wrong.
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    # Same error for both cases — prevents user enumeration
    if not user:
        raise InvalidCredentialsError()

    if not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError()

    if not user.is_active:
        raise InvalidCredentialsError()

    token = create_access_token(data={"sub": str(user.id)})
    return user, token
