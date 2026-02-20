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

---

## Phase 3: Accounts + Role-Based Access Control (2026-02-18)

### User Prompts
- **"Account holders should only be able to access their own accounts. Admin user can view
  all balances and transactions but cannot interact. Create tests."**: Added role-based
  access control with two access levels: MEMBER (own data only) and ADMIN (read-only all data).
- **"Is there a way to enforce admin accounts not having access to account holder endpoints?"**:
  Added check in `get_current_account_holder` dependency that blocks ADMIN users from all
  member banking endpoints (403). Single check point protects all member routes.
- **"I'd like the admin to be able to view individual transactions as well across all accounts"**:
  Noted for Phase 4 — admin transaction viewing will be added when Transaction model is built.
- **"Before we continue, I want to verify whether the user ID is coming from the JWT"**:
  Traced the full auth chain: JWT `sub` claim → `get_current_user` → `get_current_account_holder`.
  Confirmed user ID comes exclusively from the cryptographically signed JWT, not from client input.
- **"Before we continue, I want to retrieve a signup member's information within the test database"**:
  Ran a script against an in-memory test DB to inspect stored User and AccountHolder records.
  Verified Argon2id password hashing and correct field storage.

### Action Report
- Created `app/models/account.py` — Account model with CHECK constraint for non-negative balance
- Created `app/schemas/account.py` — AccountCreateRequest, AccountResponse, BalanceResponse
- Created `app/services/account_service.py` — account CRUD with ownership enforcement + admin read-only functions
- Created `app/routers/accounts.py` — member endpoints (POST/GET /accounts) + admin endpoints (GET /accounts/admin/*)
- Updated `app/dependencies.py` — added `require_admin` dependency, blocked admins from member endpoints
- Updated `app/models/account_holder.py` — added `accounts` relationship to Account
- Updated `tests/conftest.py` — added `admin_client` and `second_authenticated_client` fixtures
- Created `tests/test_accounts.py` — 24 tests covering creation, retrieval, ownership, admin read-only, role enforcement
- All 40 tests passing (16 auth + 24 accounts)

---

## Phase 4: Transactions + Transfers (2026-02-18)

### User Prompts
- **"I want the admin to be able to view all transactions at once across org. Same for account
  balances. Should be possible through these endpoints, but do we need additional ones for
  these aggregates?"**: Added org-wide admin endpoints: `GET /admin/transactions` (all
  transactions), `GET /admin/transactions/{id}` (any single transaction),
  `GET /admin/accounts/{id}/transactions` (any account's transactions).
- **"Add concurrent transactions testing for different account holders making transactions at
  same time"**: Added `TestConcurrentTransactions` with 3 tests: concurrent deposits to
  different accounts, concurrent debits to the same account, and concurrent mixed operations.
  Tests note SQLite limitations (no row-level locking) while validating concurrent-safe patterns.
- **"I want additional test cases: 1) tests for mid-transaction crash, 2) test to handle
  intra-user transfer"**: Added `TestTransferAtomicity` (crash simulation, orphaned transaction
  detection, audit trail) and `test_intra_user_checking_to_savings` for same-user transfers.
- **"I like the second approach with the transfer_pair_id"** (re: scoping transfer legs):
  Changed transfer transactions so each leg only sets its own account — debit sets
  `from_account_id`, credit sets `to_account_id`, both linked by `transfer_pair_id`.

### Action Report
- Created `app/models/transaction.py` — Transaction model with CHECK constraint (amount > 0),
  indexed `created_at` for statement queries, `transfer_pair_id` for linking transfer legs
- Created `app/schemas/transaction.py` — TransactionCreateRequest, TransactionResponse,
  TransferRequest (with same-account validation), TransferResponse
- Created `app/services/transaction_service.py` — **the most critical file**: `create_transaction()`
  (balance enforcement, declined audit trail), `create_transfer()` (deadlock prevention via sorted
  UUID locking, atomic paired transactions), admin read-only functions
- Created `app/routers/transactions.py` — member endpoints for create/list/get transactions
- Created `app/routers/transfers.py` — POST /transfers (atomic two-leg transfer)
- Created `app/routers/admin.py` — **consolidated all admin routes** into a dedicated router
  mounted at `/admin` to avoid route-ordering conflicts (FastAPI matches parameterized routes
  like `/{account_id}` before literal routes like `/admin` when they share a prefix)
- Updated `app/database.py` — `get_db()` now commits on `BankAPIError` (business logic errors)
  so declined transactions are persisted for the audit trail, while still rolling back on
  unexpected errors
- Updated `app/main.py` — registered admin router at `/admin` prefix, removed admin routes from
  accounts and transactions routers
- Created `tests/test_transactions.py` — 17 tests: deposits, purchases, insufficient balance
  rejection, declined transaction audit trail, listing/filtering, balance integrity,
  concurrent transactions, admin access
- Created `tests/test_transfers.py` — 16 tests: intra-user transfers (checking↔savings),
  inter-user transfers, insufficient funds, same-account rejection, cross-user authorization,
  nonexistent account handling, atomicity (crash rollback, no orphaned transactions),
  declined audit trail, balance integrity verification, admin blocked from transfers
- All 73 tests passing (16 auth + 24 accounts + 17 transactions + 16 transfers)

### Key Bugs Found & Fixed
1. **Route-ordering conflict**: Admin routes (`/admin/transactions`) were matched as
   `/{account_id}/transactions` with `account_id="admin"` → UUID parse error (422).
   Fix: consolidated all admin routes into a dedicated `/admin` router.
2. **Declined transactions lost**: `get_db()` rolled back ALL exceptions, including business
   logic errors. Declined transactions were created but then rolled back before the response.
   Fix: `get_db()` now commits on `BankAPIError` subclasses.
3. **Transfer legs over-scoped**: Both debit and credit transactions had `from_account_id`
   and `to_account_id` set, causing both legs to appear in the source account's transaction
   list. Fix: each leg now only sets its own account field; `transfer_pair_id` links them.

---

## Phase 5: Cards (2026-02-18)

### User Prompts
- **"Users should be able to 'use' cards for purchases. Transactions using cards should
  showcase the card that was used. Only cards that account holder owns can be used, and
  only cards linked to an account can pull funds from that account."**: Added `card_id`
  field to Transaction model and schema. Transaction service validates that the card
  belongs to the account, is active, and is only used on debit (not credit) transactions.
- **"'Paying off' a card should just be a debit from the account associated with that card.
  Not sure if we need temporary balances for cards — what do you think?"**: Discussed two
  models: debit card (card is payment instrument, account is source of funds) vs credit card
  (card has its own balance/debt). User chose the debit card approach — simpler, card-linked
  purchases debit the account directly. Credit card model noted for ROADMAP.md.

### Action Report
- Created `app/models/card.py` — Card model with Fernet-encrypted card_number and CVV,
  plaintext last_four for display, UNIQUE constraint on account_id (one card per account)
- Created `app/schemas/card.py` — CardResponse (excludes encrypted fields)
- Created `app/services/card_service.py` — `issue_card()` (generates 16-digit number + CVV,
  encrypts with Fernet, sets 3-year expiration), `get_card()` (masked retrieval)
- Created `app/routers/cards.py` — POST/GET /accounts/{id}/card
- Updated `app/models/transaction.py` — added `card_id` FK to cards table
- Updated `app/schemas/transaction.py` — added `card_id` to request and response
- Updated `app/services/transaction_service.py` — validates card ownership, active status,
  and debit-only usage when `card_id` is provided; records card_id on declined transactions
- Updated `app/main.py` — registered cards router
- Created `tests/test_cards.py` — 18 tests: issuance, masked response, duplicate rejection,
  encrypted storage verification (decrypt from DB), debit card purchases (with/without card),
  wrong-account card rejection, credit-with-card rejection, nonexistent card, declined
  purchase audit trail with card_id, ownership enforcement, admin blocked
- All 91 tests passing (16 auth + 24 accounts + 17 transactions + 16 transfers + 18 cards)

---

## Phase 6: Statements (2026-02-18)

### User Prompts
- **"For statements, I want them produced for each account, aggregated monthly. The user
  should see every transaction if they scroll, but the aggregates should be at the top
  (beginning balance, ending balance, total transactions, etc.)"**: Designed the statement
  response with aggregate fields first (opening/closing balance, total credits/debits,
  transaction count) followed by the full chronological transaction list.

### Action Report
- Created `app/schemas/statement.py` — StatementResponse with aggregates at top, full
  transaction list at bottom
- Created `app/services/statement_service.py` — `generate_statement()` computes opening
  balance from sum of all approved transactions before the month, closing balance from
  opening + net of month's activity, aggregates credits/debits separately
- Created `app/routers/statements.py` — GET /accounts/{id}/statements?year=&month=
- Updated `app/main.py` — registered statements router
- Created `tests/test_statements.py` — 9 tests: full statement with aggregates, empty month,
  declined transactions in list but excluded from totals, chronological ordering, required
  params validation, invalid month rejection, opening balance from prior months, ownership
  enforcement, admin blocked
- All 100 tests passing (16 auth + 24 accounts + 17 transactions + 16 transfers + 18 cards + 9 statements)

---

## Phase 7: Advanced Tests (2026-02-18)

### User Prompts
- **"Add tests where non-admins try to access admin endpoints"**: Added
  `TestNonAdminBlockedFromAdminEndpoints` test class verifying that regular MEMBER
  users receive 403 on all six `/admin/*` endpoints, including when the account is
  their own (role gate fires before ownership check).

### Action Report
- Created `tests/test_precision.py` — 5 tests: integer-only amounts in responses,
  large cent values (100M cents), no rounding errors with 100 repeated 1-cent deposits,
  sum verification after mixed credits/debits, transfer preserves total money supply
  across three accounts
- Created `tests/test_authorization.py` — 18 tests across 6 test classes:
  - `TestCrossUserAccountAccess` (4 tests): cannot view, check balance, list, or deposit
    into another user's account
  - `TestCrossUserTransactionAccess` (2 tests): cannot list or view another user's transactions
  - `TestCrossUserTransferProtection` (2 tests): cannot transfer from or drain another
    user's account; verifies source balance unchanged after rejected attempt
  - `TestCrossUserCardAccess` (2 tests): cannot view or issue cards on another user's account
  - `TestCrossUserStatementAccess` (1 test): cannot request another user's statement
  - `TestNonAdminBlockedFromAdminEndpoints` (7 tests): MEMBER blocked from all 6 admin
    endpoints, including own account via admin routes (role gate before ownership check)
- Fixed `tests/conftest.py` — `second_authenticated_client` fixture now creates its own
  `AsyncClient` instance instead of sharing one with `authenticated_client`. The previous
  implementation overwrote the auth header, causing both fixtures to authenticate as the
  same user.
- All 123 tests passing (16 auth + 24 accounts + 17 transactions + 16 transfers +
  18 cards + 9 statements + 5 precision + 18 authorization)

---

## Frontend Integration + Demo Seed (2026-02-18 – 2026-02-19)

### User Prompts
- **"Frontend is in subdirectory called 'frontend'. Check .gitignore captures what we don't
  want to commit"**: Added `frontend/node_modules/`, `frontend/dist/`, `frontend/.vite/`,
  and `demo/__pycache__/` to `.gitignore`.
- **"Three changes: user_type in login response, account lookup endpoint, seed card usage"**:
  Implemented all three: `user_type` added to `TokenResponse`, new `GET /accounts/lookup`
  endpoint for cross-user transfers, seed updated with card-linked purchases and inter-user
  transfers.
- **"Alice Chen flow issues: 1) can't look up other accounts for transfers, 2) savings
  transfers missing checking debit legs, 3) only 1 month of statement data"**: Fixed all
  three: added external account lookup to Transfers.tsx, changed seed to use real transfer
  pairs for savings (creating debit/credit in both accounts), added backdating function to
  spread transactions across 2 months.
- **"Fix admin user flow via frontend"**: Login was always routing to `/dashboard`. Root cause:
  AuthContext decoded `user_type` from JWT payload (which only has `sub`). Fixed to use
  `res.user_type` from API response; login now routes admin to `/admin`, members to `/dashboard`.
- **"Update seed to show account numbers"**: Modified `create_account()` to return account
  number, seed output now prints account numbers for each user.

### Action Report
- Modified `app/schemas/auth.py` — added `user_type: str` to `TokenResponse`
- Modified `app/routers/auth.py` — login returns `user_type` from user model
- Created `app/schemas/account.py` `AccountLookupResponse` — minimal info (id, type, number)
- Added `account_service.lookup_by_account_number()` for cross-user account lookup
- Added `GET /accounts/lookup` route (placed before `/{account_id}` to avoid route conflict)
- Created `demo/seed.py` — demo seed script with 6 users (1 admin + 5 members), accounts,
  cards, historical transactions, inter-user transfers, and backdating across 2 months
- Created `demo/README.md` — credentials table and usage instructions
- Updated `frontend/src/types/api.ts` — added `AccountLookupResponse`, `user_type` in `TokenResponse`
- Updated `frontend/src/lib/api.ts` — added `accounts.lookup()` function
- Rewrote `frontend/src/pages/member/Transfers.tsx` — "External account" option with
  account number input and lookup button for cross-user transfers
- Updated `frontend/src/contexts/AuthContext.tsx` — login uses `res.user_type` directly
  instead of JWT decode; returns user type for routing
- Updated `frontend/src/pages/Login.tsx` — routes admin to `/admin`, members to `/dashboard`
- All 123 tests passing after all changes

### Key Bugs Found & Fixed
1. **CORS blocking frontend**: Lovable preview domain not in ALLOWED_ORIGINS. Temporarily
   set to `["*"]` for development, later tightened for production.
2. **Streamlit app.py import collision**: `demo/app.py` (Streamlit) collided with `app/`
   package when running seed script. Deleted Streamlit file.
3. **Savings transfer legs missing in checking**: Seed created standalone credits labeled
   "Monthly savings transfer" — no corresponding debit in checking. Fixed to use real
   `do_transfer()` calls creating proper debit/credit pairs.
4. **Backdating UUID type mismatch**: Transaction IDs from API are strings, but SQLAlchemy
   expected UUID objects for the WHERE clause. Fixed with `uuid.UUID(txn_id)`.
5. **Admin login routed to member dashboard**: AuthContext decoded user_type from JWT payload
   (only has `sub` claim). Fixed to use `res.user_type` from TokenResponse.

---

## Phase 8: Docker + Production Hardening (2026-02-19)

### User Prompts
- **"Prep this repo to be sent as a docker image to hosting service. Backend and frontend
  can be managed by separate services"**: Created two-service Docker setup with separate
  Dockerfiles for backend (Python/uvicorn) and frontend (Node build + nginx serve).
- **"Turn off echo for SQL engine. Uvicorn --reload should not be part of production build.
  CORS adjusted so it can't handle any connection, just the ones we have specified"**:
  Verified SQL echo is controlled by `DEBUG` flag (already `echo=settings.DEBUG`). Docker
  CMD uses plain `uvicorn` without `--reload`. Locked down CORS to specific origins in
  both `.env` and `docker-compose.yml`.
- **"Create a subdirectory for documentation with placeholder files"**: Created `docs/`
  with SECURITY.md and ROADMAP.md placeholders.

### Action Report
- Created `Dockerfile.backend` — Python 3.11-slim, non-root user, uvicorn on :8000
- Created `Dockerfile.frontend` — two-stage build: node:20 builds Vite app, nginx:alpine
  serves static files with API reverse proxy
- Created `nginx.conf` — SPA fallback, `/api/*` proxied to backend service
- Created `docker-compose.yml` — two services, SQLite volume persistence, strict CORS,
  DEBUG=false, secrets via env vars
- Created `.dockerignore` — excludes .venv, tests, data, node_modules
- Updated `.env` — `DEBUG=false`, CORS locked to `localhost:8080`, `localhost:80`, `localhost`
- Updated `.env.example` — matches production-ready defaults
- Docker build and startup verified: both services run, API health check passes through
  nginx proxy, signup/login flow works end-to-end
- Created `docs/SECURITY.md` and `docs/ROADMAP.md` placeholder files
- Updated `AI_USAGE_LOG.md` with all sessions through Phase 8
- All 123 tests passing

---

## Deployment + Live Testing (2026-02-19)

### User Prompts
- **"I want to host this project (backend on Railway and frontend on Vercel). Walk me
  through steps"**: Provided step-by-step deployment guide for both platforms. Discussed
  SQLite persistence on Railway (Railway Volume at `/app/data`).
- **"Create files first"**: Created `railway.toml` (Dockerfile path, start command,
  healthcheck) and `frontend/vercel.json` (API rewrites to Railway backend, SPA fallback).
- **"Let's just do the CLI"**: Installed Railway CLI, created project `bank-infra-exercise`,
  added backend service with environment variables, attached persistent volume at `/app/data`,
  generated domain, deployed.
- **"Why aren't we using github link?"**: Linked Railway service to GitHub repo via dashboard
  for auto-deploy on push to main.
- **Railway healthcheck failure — invalid port**: `railway.toml` used `${PORT:-8000}` shell
  expansion which Railway doesn't support. Fixed to hardcode `--port 8000` and set `PORT=8000`
  as Railway variable.
- **SQLite "unable to open database file"**: Railway volume mount overrode directory ownership,
  non-root `appuser` couldn't write. Removed non-root user from Dockerfile (Railway handles
  container isolation at platform level).
- **Vercel build failed — CSS @import order**: `@import` must precede `@tailwind` directives.
  Moved font import to top of `index.css`.
- **Vercel build failed — missing `frontend/src/lib/`**: Root `.gitignore` had `lib/` (Python
  template rule) which caught `frontend/src/lib/`. Changed to `/lib/` to only match root-level.
  Three files were missing from git: `api.ts`, `format.ts`, `utils.ts`.
- **"I want to seed the demo data"**: Ran seed script against Railway backend using
  `--base-url https://backend-production-48d37.up.railway.app`. All users, accounts,
  transactions, and cards seeded successfully.
- **Admin login routing to member dashboard on deployed site**: `promote_to_admin()` in seed
  script connected to local SQLite (via `settings.DATABASE_URL`) instead of Railway's DB.
  Admin user was created as member on Railway. Created `demo/promote_admin.py`, added `demo/`
  to Docker image (removed from `.dockerignore`), ran via `railway ssh` to promote admin.
- **"Run all backend tests one last time"**: All 123 tests passed in 8.4s.

### Action Report
- Created `railway.toml` — build config pointing to `Dockerfile.backend`, healthcheck at `/health`
- Created `frontend/vercel.json` — `/api/*` rewrite to Railway backend URL, SPA fallback
- Installed Railway CLI, created project + backend service via CLI
- Set Railway environment variables: DATABASE_URL, SECRET_KEY, CARD_ENCRYPTION_KEY,
  ACCESS_TOKEN_EXPIRE_MINUTES, DEBUG, ALLOWED_ORIGINS, PORT
- Attached Railway Volume at `/app/data` for SQLite persistence
- Generated Railway domain: `backend-production-48d37.up.railway.app`
- Fixed `railway.toml` start command (hardcoded port instead of shell expansion)
- Removed non-root user from `Dockerfile.backend` for Railway volume compatibility
- Fixed `.gitignore` `lib/` → `/lib/` to stop excluding `frontend/src/lib/`
- Moved CSS `@import` before `@tailwind` directives in `frontend/src/index.css`
- Updated `vercel.json` with actual Railway backend URL
- Updated Railway CORS to include `https://bank-infra-exercise.vercel.app`
- Seeded demo data against Railway backend
- Created `demo/promote_admin.py` and ran on Railway container via SSH
- Fixed `AuthContext.tsx` — added `state.userType` to useEffect deps for admin login flow
- Removed `demo/` from `.dockerignore`, added `COPY demo/` to Dockerfile
- All 123 backend tests passing

### Key Bugs Found & Fixed
1. **Railway port parsing**: `${PORT:-8000}` shell expansion not supported in Railway
   `startCommand`. Hardcoded to `--port 8000`.
2. **Volume permissions**: Railway volume mount as root made `/app/data` unwritable for
   non-root container user. Removed `USER appuser` from Dockerfile.
3. **CSS @import order**: Vite/Vercel strict mode requires `@import` before other statements.
4. **`.gitignore` `lib/` too broad**: Python template rule caught `frontend/src/lib/`,
   preventing 3 critical frontend files from being committed.
5. **Seed admin promotion ran locally**: `promote_to_admin()` used `settings.DATABASE_URL`
   which resolved to local SQLite, not Railway's. Created separate promote script and ran
   via `railway ssh`.
6. **Admin login race condition**: `useEffect` in AuthContext only depended on
   `isAuthenticated`, not `userType`, so switching user types didn't re-trigger profile logic.
