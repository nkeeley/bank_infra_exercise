"""
Tests for integer-cent precision — no floating point anywhere.

These tests verify that the system uses integer arithmetic exclusively
for monetary amounts. Floating point representations of money cause
rounding errors (e.g., 0.1 + 0.2 = 0.30000000000000004). By storing
everything in integer cents, we guarantee exact arithmetic.

Tests verify:
  - All amounts are integers in responses
  - Large cent values work correctly
  - Repeated small transactions don't accumulate rounding errors
  - Balance = exact sum of all approved transactions
"""

import pytest


class TestIntegerCentPrecision:
    """Tests that all monetary operations use integer cents exactly."""

    async def test_all_amounts_are_integers(self, authenticated_client):
        """Every monetary field in the response should be an integer, never a float."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        txn = await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 1050},
        )
        data = txn.json()
        assert isinstance(data["amount_cents"], int)

        balance = await authenticated_client.get(f"/accounts/{account_id}/balance")
        bal_data = balance.json()
        assert isinstance(bal_data["cached_balance_cents"], int)
        assert isinstance(bal_data["computed_balance_cents"], int)

    async def test_large_values(self, authenticated_client):
        """System should handle large cent values without overflow or precision loss."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        # Deposit $1,000,000.00 (100 million cents)
        large_amount = 100_000_000
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": large_amount},
        )

        balance = await authenticated_client.get(f"/accounts/{account_id}/balance")
        assert balance.json()["cached_balance_cents"] == large_amount

        # Withdraw $999,999.99
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "debit", "amount_cents": 99_999_999},
        )

        balance = await authenticated_client.get(f"/accounts/{account_id}/balance")
        assert balance.json()["cached_balance_cents"] == 1  # Exactly 1 cent left

    async def test_no_rounding_errors_with_repeated_small_transactions(self, authenticated_client):
        """Repeated small amounts should sum exactly — no floating point drift.

        In floating point: 0.10 * 100 might not equal 10.00 exactly.
        In integer cents: 10 * 100 = 1000 always.
        """
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        # Deposit 1 cent, 100 times
        for _ in range(100):
            await authenticated_client.post(
                f"/accounts/{account_id}/transactions",
                json={"type": "credit", "amount_cents": 1},
            )

        balance = await authenticated_client.get(f"/accounts/{account_id}/balance")
        assert balance.json()["cached_balance_cents"] == 100  # Exactly $1.00

    async def test_sum_verification_after_mixed_operations(self, authenticated_client):
        """Balance should be the exact sum of credits minus debits."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        # Amounts that would cause floating point issues if stored as dollars
        # $33.33, $66.67, $16.66, $8.34 — these don't add up cleanly in float
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 3333},
        )
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 6667},
        )
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "debit", "amount_cents": 1666},
        )
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "debit", "amount_cents": 834},
        )

        # Expected: 3333 + 6667 - 1666 - 834 = 7500
        balance = await authenticated_client.get(f"/accounts/{account_id}/balance")
        data = balance.json()
        assert data["cached_balance_cents"] == 7500
        assert data["computed_balance_cents"] == 7500
        assert data["match"] is True

    async def test_transfer_preserves_total_money_supply(self, authenticated_client):
        """After transfers, the total cents across all accounts should be unchanged.

        This is the fundamental invariant of double-entry bookkeeping:
        money is never created or destroyed, only moved.
        """
        acct_a = await authenticated_client.post("/accounts", json={})
        acct_b = await authenticated_client.post("/accounts", json={})
        acct_c = await authenticated_client.post("/accounts", json={})
        a_id = acct_a.json()["id"]
        b_id = acct_b.json()["id"]
        c_id = acct_c.json()["id"]

        # Deposit $100 into A (total money supply = 10000)
        await authenticated_client.post(
            f"/accounts/{a_id}/transactions",
            json={"type": "credit", "amount_cents": 10000},
        )

        # Transfer A→B $30, A→C $20, B→C $10
        await authenticated_client.post(
            "/transfers",
            json={"from_account_id": a_id, "to_account_id": b_id, "amount_cents": 3000},
        )
        await authenticated_client.post(
            "/transfers",
            json={"from_account_id": a_id, "to_account_id": c_id, "amount_cents": 2000},
        )
        await authenticated_client.post(
            "/transfers",
            json={"from_account_id": b_id, "to_account_id": c_id, "amount_cents": 1000},
        )

        # Total should still be $100
        bal_a = await authenticated_client.get(f"/accounts/{a_id}/balance")
        bal_b = await authenticated_client.get(f"/accounts/{b_id}/balance")
        bal_c = await authenticated_client.get(f"/accounts/{c_id}/balance")

        total = (
            bal_a.json()["cached_balance_cents"]
            + bal_b.json()["cached_balance_cents"]
            + bal_c.json()["cached_balance_cents"]
        )
        assert total == 10000  # Money supply unchanged

        # Individual balances: A=5000, B=2000, C=3000
        assert bal_a.json()["cached_balance_cents"] == 5000
        assert bal_b.json()["cached_balance_cents"] == 2000
        assert bal_c.json()["cached_balance_cents"] == 3000
