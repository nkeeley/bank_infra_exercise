"""
Database engine, session management, and base model class.

This module sets up SQLAlchemy 2.0 with async support. Key components:

  - engine: The async database engine (connection pool for production DBs)
  - AsyncSessionLocal: Factory for creating async database sessions
  - Base: Declarative base class that all ORM models inherit from
  - get_db(): FastAPI dependency that provides a session per request

Architecture note:
  We use async SQLAlchemy (with aiosqlite for SQLite) so the API can handle
  concurrent requests without blocking. When migrating to PostgreSQL, only
  the DATABASE_URL needs to change (to use asyncpg driver).

Session lifecycle:
  Each API request gets its own session via get_db(). The session auto-commits
  on success and rolls back on exception, ensuring data consistency.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings
from app.exceptions import BankAPIError


# Create the async engine.
# echo=True in debug mode logs all SQL statements — invaluable for development.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
)

# Session factory: creates new AsyncSession instances.
# expire_on_commit=False prevents lazy-load errors after commit —
# without this, accessing attributes on a committed object would trigger
# a synchronous DB call, which fails in async context.
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    All models inherit from this class, which provides:
      - Automatic table name generation (from class name)
      - Metadata tracking for Alembic migrations
      - Common declarative mapping features
    """
    pass


async def get_db():
    """
    FastAPI dependency that provides a database session.

    Usage in a route:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...

    The session is automatically committed on success and rolled back
    on any exception, then closed when the request completes.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except BankAPIError:
            # Business logic errors (e.g., InsufficientFundsError) — commit the
            # session so audit-trail records (like declined transactions) are persisted.
            await session.commit()
            raise
        except Exception:
            await session.rollback()
            raise
