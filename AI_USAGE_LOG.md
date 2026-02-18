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
- Created `app/security.py` (password hashing with bcrypt, JWT creation/verification)
- Created `app/exceptions.py` (custom exception classes + FastAPI exception handlers)
- Created package `__init__.py` files
- Installed dependencies and verified health endpoint responds
