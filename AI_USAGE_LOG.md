# AI Usage Log

This document tracks all AI-assisted development in this project. Each entry includes
the user prompt (summarized) and a brief action report of what was generated or changed.

---

## Session 1: Project Planning (2026-02-17)

### Prompt 1 — Initial Requirements
> User provided core service requirements: REST service for a bank with signup, auth,
> account holders, accounts, transactions, money transfer, cards, and statements.
> SQLite database, comprehensive test suite, Python FastAPI, Docker deployment.
> Security-first approach, educational comments, organized directory structure,
> documentation (README, SECURITY, ROADMAP, AI_USAGE_LOG).

**Action:** Acknowledged requirements, confirmed understanding of deliverables and constraints.

### Prompt 2 — Business Logic Constraints
> User specified: user-based access control (IT Admin + account holders), multiple
> accounts per holder, balance = sum of transactions, atomic transaction blocks,
> monthly statements, one card per account, transaction schema (type, to/from account,
> date, ID, status), integer cents for monetary amounts, password hashing, no negative
> balances, SQLAlchemy 2.0 style ORM, specific test cases (insufficient balance,
> auth failure, concurrency, rounding errors).

**Action:** Confirmed understanding. Proposed cached + computed balance pattern,
admin bootstrapping via CLI, and pending-approval signup flow.

### Prompt 3 — Simplify Auth (Remove IT Admin)
> User requested removing IT Admin role for simplicity. Standard bank-style
> self-service authentication instead.

**Action:** Simplified to direct signup/login flow with JWT. No admin role, no
approval queue. Users are immediately active upon registration.

### Prompt 4 — Plan Approval
> User approved the implementation plan after requesting that AI_USAGE_LOG.md be
> updated continuously throughout every phase, not just at the end.

**Action:** Created 8-phase implementation plan covering ~48 files. Plan includes:
directory structure, database schema (5 tables), 17 API endpoints, 9 test files,
Docker setup, and documentation. AI_USAGE_LOG.md updated every phase.

---

## Phase 1: Foundation (2026-02-17)

### Action Report
- Created project directory structure (`app/`, `tests/`, `migrations/`, etc.)
- Created `pyproject.toml` with all dependencies
- Created `.env.example` with placeholder configuration
- Created `app/config.py` (Pydantic Settings)
- Created `app/database.py` (async SQLAlchemy engine, session, Base)
- Created `app/main.py` (FastAPI app factory with lifespan, health endpoint)
- Created `app/security.py` (password hashing with Argon2id, JWT creation/verification)
- Created `app/exceptions.py` (custom exception classes + FastAPI exception handlers)
- Created package `__init__.py` files
- Installed dependencies and verified health endpoint responds

### User Feedback During Phase 1
- **"Use argon2 instead if possible"**: Switched password hashing from bcrypt to Argon2id.
  Argon2id is the winner of the Password Hashing Competition and is resistant to both
  GPU-based and side-channel attacks.
- **"I'd like to create a virtual environment before we install dependencies"**: Created
  `.venv` virtual environment before installing packages.
- **"Run again"** (re: secret generation): Regenerated fresh SECRET_KEY and CARD_ENCRYPTION_KEY
  for the local `.env` file.

---

## Phase 2: Auth + Users (2026-02-17)

### User Prompts
- **"Adjust so that the user type is defined (e.g. Admin, Bank Employee, Bank Member)"**:
  Added `UserType` enum (ADMIN, EMPLOYEE, MEMBER) to the User model with a `user_type`
  column. Default is MEMBER for self-service signup. ADMIN and EMPLOYEE are defined for
  enterprise readiness but not enforced in MVP auth flow.
- **"First verify that token and passwords aren't being stored in debug logs"**: Conducted
  security audit of logging. Confirmed: (1) SQLAlchemy echo mode only logs hashed passwords,
  never plaintext; (2) uvicorn only logs method/path/status, not request bodies; (3) no
  request body logging middleware is installed; (4) JWT tokens only appear in response bodies,
  which are not logged. Added security audit notes to the auth router docstring.
- **"Add a test for adjusting data that would breach security (aka email)"**: Added
  `TestProfileSecurity` test class with tests verifying that email cannot be changed via
  PATCH /account-holders/me (prevents account takeover via stolen token).

### Action Report
- Created `app/models/user.py` — User model with UserType enum (ADMIN/EMPLOYEE/MEMBER)
- Created `app/models/account_holder.py` — AccountHolder model (one-to-one with User)
- Created `app/schemas/auth.py` — signup/login request/response schemas
- Created `app/schemas/user.py` — UserResponse schema (excludes password hash)
- Created `app/schemas/account_holder.py` — profile response and update schemas
- Created `app/services/auth_service.py` — signup and login business logic
- Created `app/dependencies.py` — JWT validation, get_current_user, get_current_account_holder
- Created `app/routers/auth.py` — POST /auth/signup, POST /auth/login
- Created `app/routers/account_holders.py` — GET/PATCH /account-holders/me
- Created `tests/conftest.py` — test fixtures (in-memory SQLite, client, authenticated_client)
- Created `tests/test_auth.py` — 16 tests covering signup, login, token validation, profile security
- All 16 tests passing
