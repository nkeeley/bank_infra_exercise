"""
Test fixtures for the Bank API test suite.

This module provides shared fixtures used across all test files:

  - db_engine / db_session: Fresh in-memory SQLite database for each test
  - client: Async HTTP test client (unauthenticated)
  - authenticated_client: Test client with a pre-registered MEMBER user and JWT
  - admin_client: Test client with a pre-registered ADMIN user and JWT
  - second_authenticated_client: A second MEMBER user for cross-user tests

Key design decisions:
  - In-memory SQLite (sqlite+aiosqlite://) is used for speed and isolation.
    Each test gets a completely fresh database — no state leaks between tests.
  - We override FastAPI's get_db dependency to inject our test session,
    so the application code works exactly as it does in production.
  - The authenticated_client fixture creates a user via the signup endpoint,
    so it exercises the real signup flow (not just DB inserts).
  - The admin_client fixture creates an admin by signing up normally and
    then directly updating user_type in the DB — this simulates the
    enterprise pattern where admins are provisioned by a system operator.
"""

import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.user import User, UserType


# In-memory SQLite for fast, isolated tests
TEST_DATABASE_URL = "sqlite+aiosqlite://"


@pytest_asyncio.fixture
async def db_engine():
    """Create a fresh async engine with all tables for each test."""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Provide an async session bound to the test engine."""
    async_session = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine):
    """
    Async HTTP test client with the test database injected.

    This overrides the get_db dependency so all requests hit the
    in-memory test database instead of the real one.
    """
    async_session = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db():
        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authenticated_client(client):
    """
    Test client with a pre-registered user and JWT token.

    Signs up a test user via the real signup endpoint, then sets the
    Authorization header on the client for all subsequent requests.
    """
    response = await client.post(
        "/auth/signup",
        json={
            "email": "testuser@example.com",
            "password": "SecurePass123!",
            "first_name": "Test",
            "last_name": "User",
        },
    )
    assert response.status_code == 201, f"Signup failed: {response.text}"
    token = response.json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest_asyncio.fixture
async def admin_client(client, db_engine):
    """
    Test client with a pre-registered ADMIN user and JWT token.

    Creates a user via the normal signup endpoint, then directly updates
    the user_type to ADMIN in the database. This simulates the enterprise
    pattern where admin accounts are provisioned by a system operator
    (not self-service).

    The admin can view all accounts/balances/transactions but cannot
    create accounts, initiate transfers, or modify data.
    """
    # Sign up as a normal member
    signup_response = await client.post(
        "/auth/signup",
        json={
            "email": "admin@example.com",
            "password": "AdminPass123!",
            "first_name": "Admin",
            "last_name": "User",
        },
    )
    assert signup_response.status_code == 201
    user_id = uuid.UUID(signup_response.json()["user_id"])

    # Promote to admin directly in the database
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False,
    )
    async with async_session() as session:
        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(user_type=UserType.ADMIN)
        )
        await session.commit()

    # Log in again to get a fresh token (user_type doesn't affect JWT payload,
    # but this ensures the test flow is realistic)
    login_response = await client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123!"},
    )
    admin_token = login_response.json()["token"]
    client.headers["Authorization"] = f"Bearer {admin_token}"
    return client


@pytest_asyncio.fixture
async def second_authenticated_client(client):
    """
    A second authenticated MEMBER user for cross-user authorization tests.

    Use this alongside authenticated_client to verify that User A
    cannot access User B's accounts/data.
    """
    response = await client.post(
        "/auth/signup",
        json={
            "email": "seconduser@example.com",
            "password": "SecurePass456!",
            "first_name": "Second",
            "last_name": "User",
        },
    )
    assert response.status_code == 201
    token = response.json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
