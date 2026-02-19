"""
Tests for authorization boundaries — cross-user isolation and role enforcement.

These tests verify two critical security properties:

1. **Cross-user isolation**: A logged-in MEMBER cannot access, modify, or
   even detect the existence of another user's accounts, transactions,
   cards, or statements. Every attempt should return 403 or 404.

2. **Role enforcement**: Regular MEMBER users cannot access any /admin/*
   endpoints. Only users with ADMIN role should be able to reach these
   read-only org-wide endpoints.

Together, these tests ensure that authentication alone is insufficient —
the system enforces *authorization* (who can do what) at every endpoint.
"""

import uuid

import pytest


class TestCrossUserAccountAccess:
    """A logged-in user cannot see or modify another user's accounts."""

    async def test_cannot_view_other_users_account(
        self, authenticated_client, second_authenticated_client
    ):
        """User B cannot retrieve User A's account details."""
        acct = await authenticated_client.post("/accounts", json={})
        account_id = acct.json()["id"]

        resp = await second_authenticated_client.get(f"/accounts/{account_id}")
        assert resp.status_code == 403

    async def test_cannot_view_other_users_balance(
        self, authenticated_client, second_authenticated_client
    ):
        """User B cannot check User A's balance."""
        acct = await authenticated_client.post("/accounts", json={})
        account_id = acct.json()["id"]

        resp = await second_authenticated_client.get(f"/accounts/{account_id}/balance")
        assert resp.status_code == 403

    async def test_cannot_list_other_users_accounts(
        self, authenticated_client, second_authenticated_client
    ):
        """Each user's account list only contains their own accounts."""
        await authenticated_client.post("/accounts", json={})
        await second_authenticated_client.post("/accounts", json={})

        user_a_list = await authenticated_client.get("/accounts")
        user_b_list = await second_authenticated_client.get("/accounts")

        a_ids = {a["id"] for a in user_a_list.json()}
        b_ids = {b["id"] for b in user_b_list.json()}

        # No overlap — each user only sees their own
        assert a_ids.isdisjoint(b_ids)

    async def test_cannot_deposit_into_other_users_account(
        self, authenticated_client, second_authenticated_client
    ):
        """User B cannot credit User A's account."""
        acct = await authenticated_client.post("/accounts", json={})
        account_id = acct.json()["id"]

        resp = await second_authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 5000},
        )
        assert resp.status_code == 403


class TestCrossUserTransactionAccess:
    """A user cannot view or list another user's transactions."""

    async def test_cannot_list_other_users_transactions(
        self, authenticated_client, second_authenticated_client
    ):
        """User B cannot list User A's transactions."""
        acct = await authenticated_client.post("/accounts", json={})
        account_id = acct.json()["id"]

        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 1000},
        )

        resp = await second_authenticated_client.get(
            f"/accounts/{account_id}/transactions"
        )
        assert resp.status_code == 403

    async def test_cannot_view_other_users_single_transaction(
        self, authenticated_client, second_authenticated_client
    ):
        """User B cannot retrieve a specific transaction from User A's account."""
        acct = await authenticated_client.post("/accounts", json={})
        account_id = acct.json()["id"]

        txn = await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 1000},
        )
        txn_id = txn.json()["id"]

        resp = await second_authenticated_client.get(
            f"/accounts/{account_id}/transactions/{txn_id}"
        )
        assert resp.status_code == 403


class TestCrossUserTransferProtection:
    """Transfers between accounts respect ownership rules."""

    async def test_cannot_transfer_from_other_users_account(
        self, authenticated_client, second_authenticated_client
    ):
        """User B cannot initiate a transfer FROM User A's account."""
        acct_a = await authenticated_client.post("/accounts", json={})
        a_id = acct_a.json()["id"]

        # Fund User A's account
        await authenticated_client.post(
            f"/accounts/{a_id}/transactions",
            json={"type": "credit", "amount_cents": 10000},
        )

        # User B creates their own account
        acct_b = await second_authenticated_client.post("/accounts", json={})
        b_id = acct_b.json()["id"]

        # User B tries to transfer from A to B
        resp = await second_authenticated_client.post(
            "/transfers",
            json={"from_account_id": a_id, "to_account_id": b_id, "amount_cents": 5000},
        )
        assert resp.status_code == 403

    async def test_cannot_transfer_to_drain_other_users_account(
        self, authenticated_client, second_authenticated_client
    ):
        """User B cannot drain User A's account by specifying A as the source."""
        acct_a = await authenticated_client.post("/accounts", json={})
        a_id = acct_a.json()["id"]

        await authenticated_client.post(
            f"/accounts/{a_id}/transactions",
            json={"type": "credit", "amount_cents": 50000},
        )

        acct_b = await second_authenticated_client.post("/accounts", json={})
        b_id = acct_b.json()["id"]

        resp = await second_authenticated_client.post(
            "/transfers",
            json={"from_account_id": a_id, "to_account_id": b_id, "amount_cents": 50000},
        )
        assert resp.status_code == 403

        # Verify User A's balance is unchanged
        bal = await authenticated_client.get(f"/accounts/{a_id}/balance")
        assert bal.json()["cached_balance_cents"] == 50000


class TestCrossUserCardAccess:
    """A user cannot view or issue cards on another user's account."""

    async def test_cannot_view_other_users_card(
        self, authenticated_client, second_authenticated_client
    ):
        """User B cannot retrieve User A's card details."""
        acct = await authenticated_client.post("/accounts", json={})
        account_id = acct.json()["id"]

        await authenticated_client.post(f"/accounts/{account_id}/card")

        resp = await second_authenticated_client.get(f"/accounts/{account_id}/card")
        assert resp.status_code == 403

    async def test_cannot_issue_card_on_other_users_account(
        self, authenticated_client, second_authenticated_client
    ):
        """User B cannot issue a card on User A's account."""
        acct = await authenticated_client.post("/accounts", json={})
        account_id = acct.json()["id"]

        resp = await second_authenticated_client.post(f"/accounts/{account_id}/card")
        assert resp.status_code == 403


class TestCrossUserStatementAccess:
    """A user cannot view another user's statements."""

    async def test_cannot_view_other_users_statement(
        self, authenticated_client, second_authenticated_client
    ):
        """User B cannot request a statement for User A's account."""
        acct = await authenticated_client.post("/accounts", json={})
        account_id = acct.json()["id"]

        resp = await second_authenticated_client.get(
            f"/accounts/{account_id}/statements?year=2026&month=2"
        )
        assert resp.status_code == 403


class TestNonAdminBlockedFromAdminEndpoints:
    """Regular MEMBER users cannot access any /admin/* endpoint.

    The admin router uses `require_admin` dependency on every endpoint,
    which checks the user's role and returns 403 for non-ADMIN users.
    This test class hits every admin endpoint to verify the gate works.
    """

    async def test_member_cannot_list_all_accounts(self, authenticated_client):
        """GET /admin/accounts requires ADMIN role."""
        resp = await authenticated_client.get("/admin/accounts")
        assert resp.status_code == 403

    async def test_member_cannot_view_any_account(self, authenticated_client):
        """GET /admin/accounts/{id} requires ADMIN role."""
        fake_id = str(uuid.uuid4())
        resp = await authenticated_client.get(f"/admin/accounts/{fake_id}")
        assert resp.status_code == 403

    async def test_member_cannot_view_any_balance(self, authenticated_client):
        """GET /admin/accounts/{id}/balance requires ADMIN role."""
        fake_id = str(uuid.uuid4())
        resp = await authenticated_client.get(f"/admin/accounts/{fake_id}/balance")
        assert resp.status_code == 403

    async def test_member_cannot_list_all_transactions(self, authenticated_client):
        """GET /admin/transactions requires ADMIN role."""
        resp = await authenticated_client.get("/admin/transactions")
        assert resp.status_code == 403

    async def test_member_cannot_view_any_transaction(self, authenticated_client):
        """GET /admin/transactions/{id} requires ADMIN role."""
        fake_id = str(uuid.uuid4())
        resp = await authenticated_client.get(f"/admin/transactions/{fake_id}")
        assert resp.status_code == 403

    async def test_member_cannot_list_any_accounts_transactions(self, authenticated_client):
        """GET /admin/accounts/{id}/transactions requires ADMIN role."""
        fake_id = str(uuid.uuid4())
        resp = await authenticated_client.get(f"/admin/accounts/{fake_id}/transactions")
        assert resp.status_code == 403

    async def test_member_blocked_even_for_own_account(self, authenticated_client):
        """A MEMBER cannot use admin endpoints even for their own account.

        This verifies that the admin check happens BEFORE any account
        ownership check — the request should be rejected at the role
        gate, not at the ownership gate.
        """
        acct = await authenticated_client.post("/accounts", json={})
        account_id = acct.json()["id"]

        resp = await authenticated_client.get(f"/admin/accounts/{account_id}")
        assert resp.status_code == 403

        resp = await authenticated_client.get(f"/admin/accounts/{account_id}/balance")
        assert resp.status_code == 403

        resp = await authenticated_client.get(f"/admin/accounts/{account_id}/transactions")
        assert resp.status_code == 403
