"""
User model — the authentication identity.

Each User represents a login credential (email + hashed password) with a
defined role. The User is separate from AccountHolder intentionally:

  - User handles authentication (who are you?) and authorization (what role?)
  - AccountHolder handles banking identity (what accounts do you own?)

This separation follows the Single Responsibility Principle and makes it
straightforward to enforce role-based access control in the future.

User types:
  - ADMIN: System administrator with full access (user management, etc.)
  - EMPLOYEE: Bank employee with operational access (support, auditing, etc.)
  - MEMBER: Bank member (customer) — the default role for signup

For MVP, all users sign up as MEMBER and can self-service. The ADMIN and
EMPLOYEE roles are defined here for enterprise readiness — role-based
endpoint guards can be added without changing the data model.

The password is stored as an Argon2id hash — never in plaintext. Argon2id
is the recommended password hashing algorithm (winner of the Password
Hashing Competition 2015) because it is resistant to both GPU-based
brute-force and side-channel attacks.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserType(str, enum.Enum):
    """
    Defines the role a user holds within the banking system.

    Inherits from str so the enum value serializes naturally to JSON
    and can be stored as a simple string in the database.
    """
    ADMIN = "admin"         # System administrator — full access
    EMPLOYEE = "employee"   # Bank employee — operational access
    MEMBER = "member"       # Bank member (customer) — standard access


class User(Base):
    __tablename__ = "users"

    # Primary key: UUID provides globally unique IDs without sequential guessing
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # Email is the login identifier — must be unique and indexed for fast lookups
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    # Argon2id hash of the password (never store plaintext!)
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # User role: determines access level throughout the system
    # Defaults to MEMBER — new signups are always bank members
    user_type: Mapped[UserType] = mapped_column(
        Enum(UserType),
        default=UserType.MEMBER,
        nullable=False,
    )

    # Soft-disable: deactivated users can't log in but their data is preserved
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # --- Relationships ---
    # One-to-one with AccountHolder (uselist=False means single object, not list)
    account_holder: Mapped["AccountHolder"] = relationship(
        back_populates="user",
        uselist=False,
    )
