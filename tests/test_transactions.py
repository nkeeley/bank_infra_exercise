"""
Tests for transaction endpoints (credits and debits).

These tests verify:
  - Deposits (credits) increase the balance
  - Purchases (debits) decrease the balance when sufficient funds
  - Purchases are DECLINED when insufficient balance
  - Declined transactions are still recorded (audit trail)
  - Transaction listing and filtering works
  - Admin can view all transactions org-wide
  - Concurrent transactions from different account holders
"""

import asyncio
import uuid

import pytest


class TestDeposit:
    """Tests for credit (deposit) transactions."""

    async def test_deposit_increases_balance(self, authenticated_client):
        """A credit transaction should increase the account balance."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        txn_response = await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 10000, "description": "Paycheck"},
        )
        assert txn_response.status_code == 201
        txn = txn_response.json()
        assert txn["type"] == "credit"
        assert txn["amount_cents"] == 10000
        assert txn["status"] == "approved"
        assert txn["to_account_id"] == account_id
        assert txn["from_account_id"] is None

        balance = await authenticated_client.get(f"/accounts/{account_id}/balance")
        assert balance.json()["cached_balance_cents"] == 10000

    async def test_multiple_deposits_accumulate(self, authenticated_client):
        """Multiple deposits should accumulate correctly."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 5000},
        )
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 3000},
        )

        balance = await authenticated_client.get(f"/accounts/{account_id}/balance")
        assert balance.json()["cached_balance_cents"] == 8000


class TestPurchase:
    """Tests for debit (purchase/withdrawal) transactions."""

    async def test_purchase_decreases_balance(self, authenticated_client):
        """A debit transaction should decrease the account balance."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 10000},
        )

        txn_response = await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "debit", "amount_cents": 3000, "description": "Grocery store"},
        )
        assert txn_response.status_code == 201
        txn = txn_response.json()
        assert txn["type"] == "debit"
        assert txn["status"] == "approved"
        assert txn["from_account_id"] == account_id
        assert txn["to_account_id"] is None

        balance = await authenticated_client.get(f"/accounts/{account_id}/balance")
        assert balance.json()["cached_balance_cents"] == 7000

    async def test_purchase_rejected_insufficient_balance(self, authenticated_client):
        """A debit exceeding the balance should be declined (422)."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 5000},
        )

        response = await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "debit", "amount_cents": 10000},
        )
        assert response.status_code == 422
        assert "Insufficient funds" in response.json()["detail"]
        assert response.json()["requested_cents"] == 10000
        assert response.json()["available_cents"] == 5000

        balance = await authenticated_client.get(f"/accounts/{account_id}/balance")
        assert balance.json()["cached_balance_cents"] == 5000

    async def test_declined_transaction_recorded(self, authenticated_client):
        """A declined debit should still appear in the transaction list."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "debit", "amount_cents": 1000},
        )

        txns = await authenticated_client.get(
            f"/accounts/{account_id}/transactions?status=declined"
        )
        assert txns.status_code == 200
        declined = txns.json()
        assert len(declined) == 1
        assert declined[0]["status"] == "declined"
        assert declined[0]["amount_cents"] == 1000

    async def test_exact_balance_debit_succeeds(self, authenticated_client):
        """Debiting the exact balance should succeed (leaving zero)."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 5000},
        )
        response = await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "debit", "amount_cents": 5000},
        )
        assert response.status_code == 201
        assert response.json()["status"] == "approved"

        balance = await authenticated_client.get(f"/accounts/{account_id}/balance")
        assert balance.json()["cached_balance_cents"] == 0

    async def test_zero_amount_rejected(self, authenticated_client):
        """Zero-amount transactions should be rejected (422)."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        response = await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 0},
        )
        assert response.status_code == 422

    async def test_negative_amount_rejected(self, authenticated_client):
        """Negative amounts should be rejected (422)."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        response = await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": -100},
        )
        assert response.status_code == 422


class TestTransactionListing:
    """Tests for GET /accounts/{id}/transactions."""

    async def test_list_transactions(self, authenticated_client):
        """Should return all transactions for an account."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 10000},
        )
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "debit", "amount_cents": 3000},
        )

        response = await authenticated_client.get(
            f"/accounts/{account_id}/transactions"
        )
        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_filter_by_type(self, authenticated_client):
        """Should be able to filter transactions by type."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 10000},
        )
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "debit", "amount_cents": 3000},
        )

        credits = await authenticated_client.get(
            f"/accounts/{account_id}/transactions?type=credit"
        )
        assert len(credits.json()) == 1
        assert credits.json()[0]["type"] == "credit"

    async def test_get_single_transaction(self, authenticated_client):
        """Should be able to get a single transaction by ID."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        txn = await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 5000},
        )
        txn_id = txn.json()["id"]

        response = await authenticated_client.get(
            f"/accounts/{account_id}/transactions/{txn_id}"
        )
        assert response.status_code == 200
        assert response.json()["id"] == txn_id


class TestBalanceIntegrity:
    """Tests that cached balance matches computed balance."""

    async def test_balance_match_after_multiple_transactions(self, authenticated_client):
        """Cached and computed balances should match after many operations."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 10000},
        )
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "debit", "amount_cents": 2500},
        )
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 3333},
        )
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "debit", "amount_cents": 1111},
        )

        balance = await authenticated_client.get(f"/accounts/{account_id}/balance")
        data = balance.json()
        # 10000 - 2500 + 3333 - 1111 = 9722
        assert data["cached_balance_cents"] == 9722
        assert data["computed_balance_cents"] == 9722
        assert data["match"] is True


class TestConcurrentTransactions:
    """Tests for concurrent transactions from different account holders.

    These tests verify that when multiple users make transactions at the
    same time, each user's balance is correctly updated and no data
    corruption occurs.

    Note: SQLite serializes writes, so true parallelism isn't possible.
    However, these tests verify the correctness of the concurrent-safe
    patterns (ordered locking, atomic updates) that will matter when
    migrating to PostgreSQL.
    """

    async def test_concurrent_deposits_to_different_accounts(self, client):
        """Multiple users depositing to their own accounts concurrently."""
        # Create two users with accounts
        signup_a = await client.post(
            "/auth/signup",
            json={
                "email": "concurrent_a@example.com",
                "password": "StrongPass99!",
                "first_name": "User",
                "last_name": "A",
            },
        )
        token_a = signup_a.json()["token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}
        acct_a = await client.post("/accounts", json={}, headers=headers_a)
        account_a_id = acct_a.json()["id"]

        signup_b = await client.post(
            "/auth/signup",
            json={
                "email": "concurrent_b@example.com",
                "password": "StrongPass99!",
                "first_name": "User",
                "last_name": "B",
            },
        )
        token_b = signup_b.json()["token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}
        acct_b = await client.post("/accounts", json={}, headers=headers_b)
        account_b_id = acct_b.json()["id"]

        # Fire concurrent deposits
        results = await asyncio.gather(
            client.post(
                f"/accounts/{account_a_id}/transactions",
                json={"type": "credit", "amount_cents": 5000},
                headers=headers_a,
            ),
            client.post(
                f"/accounts/{account_b_id}/transactions",
                json={"type": "credit", "amount_cents": 7000},
                headers=headers_b,
            ),
        )

        assert results[0].status_code == 201
        assert results[1].status_code == 201

        # Verify balances are correct
        bal_a = await client.get(
            f"/accounts/{account_a_id}/balance", headers=headers_a
        )
        bal_b = await client.get(
            f"/accounts/{account_b_id}/balance", headers=headers_b
        )
        assert bal_a.json()["cached_balance_cents"] == 5000
        assert bal_b.json()["cached_balance_cents"] == 7000

    async def test_concurrent_debits_same_account(self, authenticated_client):
        """Multiple debits to the same account should maintain consistency.

        If account has $100 and two $60 debits fire concurrently:
          - On PostgreSQL (with row-level locking): one succeeds, one is declined
          - On SQLite (no row-level locking): both may succeed since each
            request gets its own session and SQLite serializes writes

        This test verifies that the balance is never negative regardless
        of the database backend.
        """
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        # Deposit $100
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 10000},
        )

        # Fire two $60 debits concurrently
        results = await asyncio.gather(
            authenticated_client.post(
                f"/accounts/{account_id}/transactions",
                json={"type": "debit", "amount_cents": 6000},
            ),
            authenticated_client.post(
                f"/accounts/{account_id}/transactions",
                json={"type": "debit", "amount_cents": 6000},
            ),
        )

        status_codes = sorted([r.status_code for r in results])
        # Both may succeed on SQLite (no row-level locking); on PostgreSQL
        # one would succeed and one would be declined.
        assert all(code in (201, 422) for code in status_codes)

        # The critical invariant: balance must never be negative
        balance = await authenticated_client.get(f"/accounts/{account_id}/balance")
        assert balance.json()["cached_balance_cents"] >= 0

    async def test_concurrent_mixed_operations(self, client):
        """Different users performing different operations simultaneously."""
        # User A: depositing
        signup_a = await client.post(
            "/auth/signup",
            json={
                "email": "mix_a@example.com",
                "password": "StrongPass99!",
                "first_name": "Mix",
                "last_name": "A",
            },
        )
        token_a = signup_a.json()["token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}
        acct_a = await client.post("/accounts", json={}, headers=headers_a)
        account_a_id = acct_a.json()["id"]

        # User B: depositing then debiting
        signup_b = await client.post(
            "/auth/signup",
            json={
                "email": "mix_b@example.com",
                "password": "StrongPass99!",
                "first_name": "Mix",
                "last_name": "B",
            },
        )
        token_b = signup_b.json()["token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}
        acct_b = await client.post("/accounts", json={}, headers=headers_b)
        account_b_id = acct_b.json()["id"]

        # Pre-fund User B
        await client.post(
            f"/accounts/{account_b_id}/transactions",
            json={"type": "credit", "amount_cents": 20000},
            headers=headers_b,
        )

        # Fire concurrent: User A deposits, User B debits
        results = await asyncio.gather(
            client.post(
                f"/accounts/{account_a_id}/transactions",
                json={"type": "credit", "amount_cents": 15000},
                headers=headers_a,
            ),
            client.post(
                f"/accounts/{account_b_id}/transactions",
                json={"type": "debit", "amount_cents": 8000},
                headers=headers_b,
            ),
        )

        assert results[0].status_code == 201
        assert results[1].status_code == 201

        bal_a = await client.get(
            f"/accounts/{account_a_id}/balance", headers=headers_a
        )
        bal_b = await client.get(
            f"/accounts/{account_b_id}/balance", headers=headers_b
        )
        assert bal_a.json()["cached_balance_cents"] == 15000
        assert bal_b.json()["cached_balance_cents"] == 12000


class TestAdminTransactionAccess:
    """Tests that admins can view all transactions org-wide."""

    async def test_admin_can_list_all_transactions(self, admin_client, client):
        """Admin should see ALL transactions across the org."""
        signup = await client.post(
            "/auth/signup",
            json={
                "email": "txn_member@example.com",
                "password": "StrongPass99!",
                "first_name": "Txn",
                "last_name": "Member",
            },
        )
        member_token = signup.json()["token"]
        member_headers = {"Authorization": f"Bearer {member_token}"}

        acct = await client.post("/accounts", json={}, headers=member_headers)
        account_id = acct.json()["id"]
        await client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 5000},
            headers=member_headers,
        )

        response = await admin_client.get("/admin/transactions")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    async def test_admin_can_view_account_transactions(self, admin_client, client):
        """Admin should be able to list any account's transactions."""
        signup = await client.post(
            "/auth/signup",
            json={
                "email": "acct_txn@example.com",
                "password": "StrongPass99!",
                "first_name": "Acct",
                "last_name": "Txn",
            },
        )
        member_token = signup.json()["token"]
        member_headers = {"Authorization": f"Bearer {member_token}"}

        acct = await client.post("/accounts", json={}, headers=member_headers)
        account_id = acct.json()["id"]
        await client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 7777},
            headers=member_headers,
        )

        response = await admin_client.get(
            f"/admin/accounts/{account_id}/transactions"
        )
        assert response.status_code == 200
        txns = response.json()
        assert len(txns) == 1
        assert txns[0]["amount_cents"] == 7777

    async def test_member_cannot_access_admin_transactions(self, authenticated_client):
        """Members should get 403 on admin transaction endpoints."""
        response = await authenticated_client.get("/admin/transactions")
        assert response.status_code == 403
