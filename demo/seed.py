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


async def create_account(client: httpx.AsyncClient, token: str, account_type: str) -> str:
    resp = await client.post(
        f"{BASE_URL}/accounts",
        json={"account_type": account_type},
        headers=auth_header(token),
    )
    resp.raise_for_status()
    return resp.json()["id"]


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

async def seed_history(client: httpx.AsyncClient, token: str, account_id: str,
                       account_type: str, months: int,
                       card_id: str | None = None) -> None:
    """Generate 2-3 months of realistic transaction history.

    If card_id is provided (checking accounts), ~60% of purchases will
    use the debit card so the frontend shows card-linked transactions.
    """
    if account_type == "checking":
        for _ in range(months):
            # 2 payroll deposits per month
            await transact(client, token, account_id, "credit",
                           random.randint(1_800_00, 3_200_00), "Payroll deposit")
            await transact(client, token, account_id, "credit",
                           random.randint(1_800_00, 3_200_00), "Payroll deposit")
            # 8-15 purchases per month
            for _ in range(random.randint(8, 15)):
                desc = random.choice(DEBIT_DESCRIPTIONS)
                amount = random.randint(3_00, 120_00)
                # Use card for ~60% of purchases
                use_card = card_id if (card_id and random.random() < 0.6) else None
                result = await transact(client, token, account_id, "debit",
                                        amount, desc, card_id=use_card)
                if result.get("status") == "declined":
                    break
    else:
        for _ in range(months):
            await transact(client, token, account_id, "credit",
                           random.randint(200_00, 800_00), "Monthly savings transfer")
            if random.random() < 0.2:
                await transact(client, token, account_id, "debit",
                               random.randint(100_00, 300_00), "Savings withdrawal")


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

            for acct_info in member.get("accounts", []):
                account_id = await create_account(client, token, acct_info["type"])
                log(f"  {acct_info['type'].capitalize()} account created")

                # Opening deposit
                await transact(client, token, account_id, "credit",
                               acct_info["initial_deposit"], "Opening deposit")
                log(f"  Opening deposit: {cents_to_dollars(acct_info['initial_deposit'])}")

                # Issue card for checking accounts BEFORE history so purchases use it
                card_id = None
                if acct_info["type"] == "checking":
                    card_id = await issue_card(client, token, account_id)
                    if card_id:
                        log(f"  Debit card issued")

                # Historical transactions (with card for ~60% of purchases)
                months = random.choice([2, 3])
                await seed_history(client, token, account_id, acct_info["type"],
                                   months, card_id=card_id)

                balance = await get_balance(client, token, account_id)
                log(f"  {months} months of history seeded. Balance: {cents_to_dollars(balance)}")

                all_accounts.append({
                    "account_id": account_id,
                    "token": token,
                    "name": name,
                    "type": acct_info["type"],
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
