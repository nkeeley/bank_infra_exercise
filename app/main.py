"""
FastAPI application factory and entry point.

This module creates and configures the FastAPI application:
  1. Lifespan manager — handles startup/shutdown (DB table creation, cleanup)
  2. CORS middleware — allows frontend origins to make cross-origin requests
  3. Exception handlers — maps domain errors to HTTP responses
  4. Router registration — mounts all API endpoint groups

Running locally:
    uvicorn app.main:app --reload

The --reload flag watches for file changes and restarts automatically,
which is ideal for development but should not be used in production.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.exceptions import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager (replaces deprecated @app.on_event).

    Startup:
      Creates all database tables if they don't exist. This is a convenience
      for development — in production, you'd use Alembic migrations exclusively
      so you have version-controlled, reversible schema changes.

    Shutdown:
      Disposes of the database engine, closing all connections cleanly.
    """
    # --- Startup ---
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # --- Shutdown ---
    await engine.dispose()


# Create the FastAPI application instance
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Banking REST API with account management, transactions, and transfers",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

# CORS: Allow specified frontend origins to make requests.
# In production, lock this down to your actual frontend domain(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

register_exception_handlers(app)

# ---------------------------------------------------------------------------
# Routers (will be added in subsequent phases)
# ---------------------------------------------------------------------------

# Phase 2: auth, account_holders
# Phase 3: accounts
# Phase 4: transactions, transfers
# Phase 5: cards
# Phase 6: statements


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for deployment probes (Kubernetes, Docker, etc.).

    Returns a simple JSON response indicating the service is running.
    Load balancers and orchestrators use this to determine if the
    container should receive traffic.
    """
    return {"status": "ok", "version": settings.APP_VERSION}
