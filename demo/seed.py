#!/usr/bin/env python3
"""
Demo seed script — populates the database with sample data for demos.

!! NOT FOR PRODUCTION !!
This script creates test users with known passwords and fake transaction
data. It is intended ONLY for local demos and frontend development.

Usage:
    # With the API server running on localhost:8000:
    python demo/seed.py

    # Reset the database and re-seed:
    python demo/seed.py --reset

    # Custom server URL:
    python demo/seed.py --base-url http://localhost:9000

Login credentials after seeding:
    ┌──────────────────────────────┬───────────────────┬────────┐
    │ Email                        │ Password          │ Role   │
    ├──────────────────────────────┼───────────────────┼────────┤
    │ admin@bankdemo.com           │ AdminDemo123!     │ ADMIN  │
    │ alice.chen@example.com       │ AliceDemo123!     │ MEMBER │
    │ bob.martinez@example.com     │ BobDemo123!       │ MEMBER │
    │ carol.nguyen@example.com     │ CarolDemo123!     │ MEMBER │
    │ dave.johnson@example.com     │ DaveDemo123!      │ MEMBER │
    │ erin.patel@example.com       │ ErinDemo123!      │ MEMBER │
    └──────────────────────────────┴───────────────────┴────────┘
"""

import argparse
import asyncio
import os
import random
import sys
from datetime import datetime, timedelta, timezone

import httpx

BASE_URL = "http://localhost:8000"

# ---------------------------------------------------------------------------
# Demo users
# ---------------------------------------------------------------------------

ADMIN = {
    "email": "admin@bankdemo.com",
    "password": "AdminDemo123!",
    "first_name": "Admin",
    "last_name": "User",
}

MEMBERS = [
    {
        "email": "alice.chen@example.com",
        "password": "AliceDemo123!",
        "first_name": "Alice",
        "last_name": "Chen",
        "accounts": [
            {"type": "checking", "initial_deposit": 850_00},
            {"type": "savings", "initial_deposit": 5_000_00},
        ],
    },
    {
        "email": "bob.martinez@example.com",
        "password": "BobDemo123!",
        "first_name": "Bob",
        "last_name": "Martinez",
        "accounts": [
            {"type": "checking", "initial_deposit": 1_200_00},
        ],
    },
    {
        "email": "carol.nguyen@example.com",
        "password": "CarolDemo123!",
        "first_name": "Carol",
        "last_name": "Nguyen",
        "accounts": [
            {"type": "checking", "initial_deposit": 3_200_00},
            {"type": "savings", "initial_deposit": 12_000_00},
        ],
    },
    {
        "email": "dave.johnson@example.com",
        "password": "DaveDemo123!",
        "first_name": "Dave",
        "last_name": "Johnson",
        "accounts": [
            {"type": "checking", "initial_deposit": 600_00},
        ],
    },
    {
        "email": "erin.patel@example.com",
        "password": "ErinDemo123!",
        "first_name": "Erin",
        "last_name": "Patel",
        "accounts": [
            {"type": "checking", "initial_deposit": 2_500_00},
        ],
    },
]

DEBIT_DESCRIPTIONS = [
    "Coffee shop", "Grocery store", "Gas station", "Online subscription",
    "Restaurant", "Utility bill", "Phone bill", "Parking", "Bookstore",
    "Pharmacy", "Hardware store", "Clothing store", "Movie tickets",
    "Gym membership", "Insurance premium", "Internet bill",
]

CREDIT_DESCRIPTIONS = [
    "Payroll deposit", "Freelance payment", "Refund", "Cash deposit",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    print(f"  {msg}")


def cents_to_dollars(cents: int) -> str:
    return f"${cents / 100:,.2f}"


async def signup(client: httpx.AsyncClient, user: dict) -> str:
    """Sign up a user, return JWT token."""
    resp = await client.post(f"{BASE_URL}/auth/signup", json={
        "email": user["email"],
        "password": user["password"],
        "first_name": user["first_name"],
        "last_name": user["last_name"],
    })
    resp.raise_for_status()
    return resp.json()["token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def create_account(client: httpx.AsyncClient, token: str, account_type: str) -> dict:
    """Create an account and return {id, account_number}."""
    resp = await client.post(
        f"{BASE_URL}/accounts",
        json={"account_type": account_type},
        headers=auth_header(token),
    )
    resp.raise_for_status()
    data = resp.json()
    return {"id": data["id"], "account_number": data["account_number"]}


async def transact(client: httpx.AsyncClient, token: str, account_id: str,
                   txn_type: str, amount_cents: int, description: str,
                   card_id: str | None = None) -> dict:
    body: dict = {"type": txn_type, "amount_cents": amount_cents, "description": description}
    if card_id:
        body["card_id"] = card_id
    resp = await client.post(
        f"{BASE_URL}/accounts/{account_id}/transactions",
        json=body,
        headers=auth_header(token),
    )
    return resp.json()


async def do_transfer(client: httpx.AsyncClient, token: str,
                      from_id: str, to_id: str, amount_cents: int, description: str) -> dict:
    resp = await client.post(
        f"{BASE_URL}/transfers",
        json={
            "from_account_id": from_id,
            "to_account_id": to_id,
            "amount_cents": amount_cents,
            "description": description,
        },
        headers=auth_header(token),
    )
    return resp.json()


async def issue_card(client: httpx.AsyncClient, token: str, account_id: str) -> str | None:
    resp = await client.post(
        f"{BASE_URL}/accounts/{account_id}/card",
        headers=auth_header(token),
    )
    if resp.status_code == 409:
        return None
    resp.raise_for_status()
    return resp.json()["id"]


async def get_balance(client: httpx.AsyncClient, token: str, account_id: str) -> int:
    resp = await client.get(
        f"{BASE_URL}/accounts/{account_id}/balance",
        headers=auth_header(token),
    )
    resp.raise_for_status()
    return resp.json()["cached_balance_cents"]


# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------

async def seed_history(
    client: httpx.AsyncClient, token: str, account_id: str,
    account_type: str, months: int,
    card_id: str | None = None,
    checking_id: str | None = None,
) -> list[str]:
    """Generate 2 months of realistic transaction history.

    Returns a list of transaction IDs created, so they can be backdated.

    If card_id is provided (checking accounts), ~60% of purchases will
    use the debit card so the frontend shows card-linked transactions.

    For savings accounts, if checking_id is provided, uses real transfers
    from checking→savings (creating debit/credit pairs in both accounts).
    """
    txn_ids: list[str] = []

    if account_type == "checking":
        for _ in range(months):
            # 2 payroll deposits per month
            for _ in range(2):
                result = await transact(client, token, account_id, "credit",
                                        random.randint(1_800_00, 3_200_00), "Payroll deposit")
                if result.get("id"):
                    txn_ids.append(result["id"])
            # 8-15 purchases per month
            for _ in range(random.randint(8, 15)):
                desc = random.choice(DEBIT_DESCRIPTIONS)
                amount = random.randint(3_00, 120_00)
                use_card = card_id if (card_id and random.random() < 0.6) else None
                result = await transact(client, token, account_id, "debit",
                                        amount, desc, card_id=use_card)
                if result.get("id"):
                    txn_ids.append(result["id"])
                if result.get("status") == "declined":
                    break
    else:
        # Savings: use real transfers from checking if available
        for _ in range(months):
            amount = random.randint(200_00, 800_00)
            if checking_id:
                result = await do_transfer(
                    client, token, checking_id, account_id,
                    amount, "Monthly savings transfer",
                )
                # Transfer creates 2 transactions; collect both IDs
                if result.get("debit_transaction"):
                    txn_ids.append(result["debit_transaction"]["id"])
                if result.get("credit_transaction"):
                    txn_ids.append(result["credit_transaction"]["id"])
            else:
                result = await transact(client, token, account_id, "credit",
                                        amount, "Monthly savings transfer")
                if result.get("id"):
                    txn_ids.append(result["id"])
            if random.random() < 0.2:
                result = await transact(client, token, account_id, "debit",
                                        random.randint(100_00, 300_00), "Savings withdrawal")
                if result.get("id"):
                    txn_ids.append(result["id"])

    return txn_ids


async def backdate_transactions(txn_ids_by_month: dict[int, list[str]]) -> None:
    """Update created_at timestamps directly in the DB to spread transactions
    across multiple months.

    txn_ids_by_month maps month_offset (0 = current, 1 = last month, etc.)
    to lists of transaction IDs that should be dated in that month.
    Within each month, transactions are spread across random days.
    """
    import uuid as uuid_mod
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.config import settings
    from app.models.transaction import Transaction

    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)

    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        for month_offset, ids in txn_ids_by_month.items():
            if not ids:
                continue
            # Target the middle of the month, offset months back
            base = now.replace(day=15) - timedelta(days=30 * month_offset)
            for txn_id in ids:
                # Random day within the month (spread across ±12 days from base)
                offset_days = random.randint(-12, 12)
                offset_hours = random.randint(8, 20)
                offset_mins = random.randint(0, 59)
                ts = base + timedelta(days=offset_days, hours=offset_hours - base.hour,
                                      minutes=offset_mins - base.minute)
                await session.execute(
                    update(Transaction)
                    .where(Transaction.id == uuid_mod.UUID(txn_id))
                    .values(created_at=ts, updated_at=ts)
                )
        await session.commit()

    await engine.dispose()


async def promote_to_admin(admin_email: str) -> None:
    """Directly update the user's role to ADMIN in the database.

    This bypasses the API since there's no admin-promotion endpoint
    (by design — admin provisioning is an operator action, not self-service).
    """
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.config import settings
    from app.models.user import User, UserType

    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)

    async with session_factory() as session:
        await session.execute(
            update(User)
            .where(User.email == admin_email)
            .values(user_type=UserType.ADMIN)
        )
        await session.commit()

    await engine.dispose()


async def seed(base_url: str) -> None:
    global BASE_URL
    BASE_URL = base_url

    print("\n========================================")
    print("  DEMO SEED — NOT FOR PRODUCTION")
    print("========================================\n")

    # Collect transaction IDs by month offset for backdating
    # month 0 = current month, month 1 = last month
    txn_ids_by_month: dict[int, list[str]] = {0: [], 1: []}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Health check
        try:
            health = await client.get(f"{BASE_URL}/health")
            health.raise_for_status()
        except (httpx.ConnectError, httpx.HTTPStatusError):
            print(f"  ERROR: Cannot connect to {BASE_URL}")
            print(f"  Start the server first: uvicorn app.main:app --reload\n")
            sys.exit(1)

        # --- Admin ---
        print("Creating admin user...")
        admin_token = await signup(client, ADMIN)
        await promote_to_admin(ADMIN["email"])
        log(f"Admin: {ADMIN['email']} / {ADMIN['password']}")

        # --- Members ---
        all_accounts: list[dict] = []  # Track for inter-user transfers

        for member in MEMBERS:
            name = f"{member['first_name']} {member['last_name']}"
            print(f"\nCreating {name}...")
            token = await signup(client, member)
            log(f"Login: {member['email']} / {member['password']}")

            # First pass: create accounts, deposits, and cards
            member_accounts: list[dict] = []
            checking_id = None
            for acct_info in member.get("accounts", []):
                acct_data = await create_account(client, token, acct_info["type"])
                account_id = acct_data["id"]
                account_number = acct_data["account_number"]
                log(f"  {acct_info['type'].capitalize()} account: {account_number}")

                # Opening deposit (always month 1 — oldest)
                result = await transact(client, token, account_id, "credit",
                                        acct_info["initial_deposit"], "Opening deposit")
                if result.get("id"):
                    txn_ids_by_month[1].append(result["id"])
                log(f"  Opening deposit: {cents_to_dollars(acct_info['initial_deposit'])}")

                card_id = None
                if acct_info["type"] == "checking":
                    checking_id = account_id
                    card_id = await issue_card(client, token, account_id)
                    if card_id:
                        log(f"  Debit card issued")

                member_accounts.append({
                    "account_id": account_id,
                    "type": acct_info["type"],
                    "card_id": card_id,
                })

            # Second pass: seed history (savings needs checking_id for real transfers)
            for acct in member_accounts:
                months = 2
                ids = await seed_history(
                    client, token, acct["account_id"], acct["type"],
                    months, card_id=acct["card_id"],
                    checking_id=checking_id if acct["type"] == "savings" else None,
                )
                # Split collected IDs across 2 months
                mid = len(ids) // 2
                txn_ids_by_month[1].extend(ids[:mid])   # older half → last month
                txn_ids_by_month[0].extend(ids[mid:])   # newer half → this month

                balance = await get_balance(client, token, acct["account_id"])
                log(f"  {acct['type'].capitalize()}: {months} months seeded. Balance: {cents_to_dollars(balance)}")

                all_accounts.append({
                    "account_id": acct["account_id"],
                    "token": token,
                    "name": name,
                    "type": acct["type"],
                })

        # --- Inter-user transfers ---
        print("\nCreating inter-user transfers...")
        checking_accounts = [a for a in all_accounts if a["type"] == "checking"]
        if len(checking_accounts) >= 2:
            # Alice -> Bob
            a, b = checking_accounts[0], checking_accounts[1]
            amount = random.randint(25_00, 100_00)
            result = await do_transfer(
                client, a["token"], a["account_id"], b["account_id"],
                amount, f"Payment from {a['name']} to {b['name']}"
            )
            if "error_type" not in result:
                log(f"{a['name']} -> {b['name']}: {cents_to_dollars(amount)}")

            # Bob -> Alice (so Alice has incoming transfers too)
            amount = random.randint(15_00, 75_00)
            result = await do_transfer(
                client, b["token"], b["account_id"], a["account_id"],
                amount, f"Payment from {b['name']} to {a['name']}"
            )
            if "error_type" not in result:
                log(f"{b['name']} -> {a['name']}: {cents_to_dollars(amount)}")

            # Alice -> Carol
            if len(checking_accounts) >= 3:
                c = checking_accounts[2]
                amount = random.randint(30_00, 150_00)
                result = await do_transfer(
                    client, a["token"], a["account_id"], c["account_id"],
                    amount, f"Payment from {a['name']} to {c['name']}"
                )
                if "error_type" not in result:
                    log(f"{a['name']} -> {c['name']}: {cents_to_dollars(amount)}")

            # Carol -> Dave
            if len(checking_accounts) >= 4:
                c, d = checking_accounts[2], checking_accounts[3]
                amount = random.randint(50_00, 200_00)
                result = await do_transfer(
                    client, c["token"], c["account_id"], d["account_id"],
                    amount, f"Payment from {c['name']} to {d['name']}"
                )
                if "error_type" not in result:
                    log(f"{c['name']} -> {d['name']}: {cents_to_dollars(amount)}")

    # --- Backdate transactions across 2 months ---
    print("\nBackdating transactions across 2 months...")
    await backdate_transactions(txn_ids_by_month)
    log(f"Month -1 (last month): {len(txn_ids_by_month[1])} transactions")
    log(f"Month  0 (this month): {len(txn_ids_by_month[0])} transactions")

    # --- Summary ---
    print("\n========================================")
    print("  SEED COMPLETE — Login Credentials")
    print("========================================")
    print(f"\n  {'Email':<30s} {'Password':<20s} {'Role'}")
    print(f"  {'─' * 30} {'─' * 20} {'─' * 6}")
    print(f"  {ADMIN['email']:<30s} {ADMIN['password']:<20s} ADMIN")
    for m in MEMBERS:
        print(f"  {m['email']:<30s} {m['password']:<20s} MEMBER")
    print()


def reset_database() -> None:
    """Delete the SQLite database file so the server recreates it on restart."""
    db_path = os.path.join(os.path.dirname(__file__), "..", "data", "bank.db")
    db_path = os.path.normpath(db_path)

    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"\n  Deleted {db_path}")
        print("  Restart the server to recreate empty tables.\n")
    else:
        print(f"\n  No database found at {db_path}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Demo seed script — NOT FOR PRODUCTION",
        epilog="Creates sample users, accounts, and transactions for demos.",
    )
    parser.add_argument(
        "--base-url", default="http://localhost:8000",
        help="Base URL of the running API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Delete the database file and exit (restart server to recreate)",
    )
    args = parser.parse_args()

    if args.reset:
        reset_database()
        return

    await seed(args.base_url)


if __name__ == "__main__":
    asyncio.run(main())
