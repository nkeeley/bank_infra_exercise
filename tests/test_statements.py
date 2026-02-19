"""
Tests for monthly statement endpoints.

These tests verify:
  - Statements include aggregates (opening/closing balance, totals)
  - Statements include the full list of transactions for the month
  - Opening balance is computed from prior months' transactions
  - Declined transactions are included in the list but not in balance totals
  - Empty months produce a valid statement with zero activity
  - Ownership enforcement
  - Admin is blocked from statement endpoints
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest


class TestStatementGeneration:
    """Tests for GET /accounts/{id}/statements?year=&month=."""

    async def test_statement_with_transactions(self, authenticated_client):
        """Statement should include aggregates and all transactions."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        # Create some transactions
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 10000, "description": "Paycheck"},
        )
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 5000, "description": "Bonus"},
        )
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "debit", "amount_cents": 3000, "description": "Groceries"},
        )

        now = datetime.now(timezone.utc)
        response = await authenticated_client.get(
            f"/accounts/{account_id}/statements",
            params={"year": now.year, "month": now.month},
        )
        assert response.status_code == 200
        data = response.json()

        # Aggregates at the top
        assert data["account_id"] == account_id
        assert data["year"] == now.year
        assert data["month"] == now.month
        assert data["opening_balance_cents"] == 0  # No prior months
        assert data["closing_balance_cents"] == 12000  # 10000 + 5000 - 3000
        assert data["total_credits_cents"] == 15000  # 10000 + 5000
        assert data["total_debits_cents"] == 3000
        assert data["transaction_count"] == 3

        # Full transaction list
        assert len(data["transactions"]) == 3

    async def test_empty_month_statement(self, authenticated_client):
        """Statement for a month with no transactions should have zero activity."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        response = await authenticated_client.get(
            f"/accounts/{account_id}/statements",
            params={"year": 2025, "month": 1},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["opening_balance_cents"] == 0
        assert data["closing_balance_cents"] == 0
        assert data["total_credits_cents"] == 0
        assert data["total_debits_cents"] == 0
        assert data["transaction_count"] == 0
        assert data["transactions"] == []

    async def test_statement_includes_declined_in_list_not_totals(self, authenticated_client):
        """Declined transactions appear in the list but don't affect balances."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        # Deposit $50
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 5000},
        )
        # Try to withdraw $100 (will be declined)
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "debit", "amount_cents": 10000},
        )

        now = datetime.now(timezone.utc)
        response = await authenticated_client.get(
            f"/accounts/{account_id}/statements",
            params={"year": now.year, "month": now.month},
        )
        data = response.json()

        # Declined transaction in the list
        assert data["transaction_count"] == 2
        statuses = [t["status"] for t in data["transactions"]]
        assert "declined" in statuses

        # But balance only reflects the approved credit
        assert data["closing_balance_cents"] == 5000
        assert data["total_credits_cents"] == 5000
        assert data["total_debits_cents"] == 0  # Declined debit excluded

    async def test_statement_transactions_ordered_chronologically(self, authenticated_client):
        """Transactions in a statement should be ordered oldest to newest."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 1000, "description": "First"},
        )
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 2000, "description": "Second"},
        )
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 3000, "description": "Third"},
        )

        now = datetime.now(timezone.utc)
        response = await authenticated_client.get(
            f"/accounts/{account_id}/statements",
            params={"year": now.year, "month": now.month},
        )
        data = response.json()

        descriptions = [t["description"] for t in data["transactions"]]
        assert descriptions == ["First", "Second", "Third"]

    async def test_missing_year_or_month_rejected(self, authenticated_client):
        """Year and month query params are required."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        # Missing both
        response = await authenticated_client.get(
            f"/accounts/{account_id}/statements"
        )
        assert response.status_code == 422

        # Missing month
        response = await authenticated_client.get(
            f"/accounts/{account_id}/statements", params={"year": 2026}
        )
        assert response.status_code == 422

    async def test_invalid_month_rejected(self, authenticated_client):
        """Month must be 1-12."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        response = await authenticated_client.get(
            f"/accounts/{account_id}/statements",
            params={"year": 2026, "month": 13},
        )
        assert response.status_code == 422

        response = await authenticated_client.get(
            f"/accounts/{account_id}/statements",
            params={"year": 2026, "month": 0},
        )
        assert response.status_code == 422


class TestStatementOpeningBalance:
    """Tests that opening balance is correctly computed from prior months."""

    async def test_opening_balance_reflects_prior_activity(self, authenticated_client):
        """Opening balance should include all approved transactions before the month.

        Since all test transactions happen in the current month, we verify
        that the opening balance for the current month is 0 (no prior months),
        and the closing balance reflects the current month's activity.
        """
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        # All activity happens "now" (current month)
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 20000},
        )
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "debit", "amount_cents": 5000},
        )

        now = datetime.now(timezone.utc)
        response = await authenticated_client.get(
            f"/accounts/{account_id}/statements",
            params={"year": now.year, "month": now.month},
        )
        data = response.json()

        assert data["opening_balance_cents"] == 0
        assert data["closing_balance_cents"] == 15000

        # Future month should see current activity as "prior"
        future_month = now.month + 1 if now.month < 12 else 1
        future_year = now.year if now.month < 12 else now.year + 1
        response = await authenticated_client.get(
            f"/accounts/{account_id}/statements",
            params={"year": future_year, "month": future_month},
        )
        data = response.json()

        assert data["opening_balance_cents"] == 15000
        assert data["closing_balance_cents"] == 15000  # No new activity
        assert data["transaction_count"] == 0


class TestStatementOwnership:
    """Tests that users can only access their own statements."""

    async def test_cannot_view_other_users_statement(self, client):
        """User B should not be able to view User A's statement."""
        signup_a = await client.post(
            "/auth/signup",
            json={
                "email": "stmt_a@example.com",
                "password": "StrongPass99!",
                "first_name": "Stmt",
                "last_name": "A",
            },
        )
        headers_a = {"Authorization": f"Bearer {signup_a.json()['token']}"}
        acct_a = await client.post("/accounts", json={}, headers=headers_a)
        account_a_id = acct_a.json()["id"]

        signup_b = await client.post(
            "/auth/signup",
            json={
                "email": "stmt_b@example.com",
                "password": "StrongPass99!",
                "first_name": "Stmt",
                "last_name": "B",
            },
        )
        headers_b = {"Authorization": f"Bearer {signup_b.json()['token']}"}

        response = await client.get(
            f"/accounts/{account_a_id}/statements",
            params={"year": 2026, "month": 1},
            headers=headers_b,
        )
        assert response.status_code == 403


class TestAdminBlockedFromStatements:
    """Tests that admins cannot access statement endpoints."""

    async def test_admin_cannot_view_statements(self, admin_client):
        """Admins should get 403 on statement endpoint."""
        fake_id = str(uuid.uuid4())
        response = await admin_client.get(
            f"/accounts/{fake_id}/statements",
            params={"year": 2026, "month": 1},
        )
        assert response.status_code == 403
