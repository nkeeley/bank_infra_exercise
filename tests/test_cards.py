"""
Tests for card endpoints (issuance, retrieval, and card-linked purchases).

These tests verify:
  - Card issuance creates a card with masked details
  - Only one card per account (duplicate rejected with 409)
  - Card details are masked (no full number or CVV in responses)
  - Card data is encrypted at rest in the database
  - Debit card purchases reference the card and debit the account
  - Card validation (wrong account, inactive card, credit with card)
  - Ownership enforcement (can't access another user's card)
  - Admin is blocked from card endpoints (member-only)
"""

import uuid

import pytest
from sqlalchemy import select

from app.models.card import Card
from app.security import decrypt_value


class TestCardIssuance:
    """Tests for POST /accounts/{id}/card."""

    async def test_issue_card_success(self, authenticated_client):
        """Issuing a card should return masked card details."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        response = await authenticated_client.post(f"/accounts/{account_id}/card")
        assert response.status_code == 201
        data = response.json()

        assert data["account_id"] == account_id
        assert len(data["card_number_last_four"]) == 4
        assert data["card_number_last_four"].isdigit()
        assert data["expiration_month"] >= 1
        assert data["expiration_month"] <= 12
        assert data["expiration_year"] >= 2029  # 3 years from now
        assert data["is_active"] is True
        assert data["id"] is not None

    async def test_card_response_has_no_sensitive_fields(self, authenticated_client):
        """Card responses must NOT contain full card number or CVV."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        response = await authenticated_client.post(f"/accounts/{account_id}/card")
        data = response.json()

        # These fields should NOT be in the response
        assert "card_number_encrypted" not in data
        assert "cvv_encrypted" not in data
        assert "card_number" not in data
        assert "cvv" not in data

    async def test_duplicate_card_rejected(self, authenticated_client):
        """Issuing a second card for the same account should fail (409)."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        first = await authenticated_client.post(f"/accounts/{account_id}/card")
        assert first.status_code == 201

        second = await authenticated_client.post(f"/accounts/{account_id}/card")
        assert second.status_code == 409
        assert "already has a card" in second.json()["detail"]

    async def test_issue_card_nonexistent_account(self, authenticated_client):
        """Issuing a card for a nonexistent account should return 404."""
        fake_id = str(uuid.uuid4())
        response = await authenticated_client.post(f"/accounts/{fake_id}/card")
        assert response.status_code == 404


class TestCardRetrieval:
    """Tests for GET /accounts/{id}/card."""

    async def test_get_card_success(self, authenticated_client):
        """Should return the card details (masked)."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        issued = await authenticated_client.post(f"/accounts/{account_id}/card")

        response = await authenticated_client.get(f"/accounts/{account_id}/card")
        assert response.status_code == 200
        data = response.json()
        assert data["account_id"] == account_id
        assert data["card_number_last_four"] == issued.json()["card_number_last_four"]

    async def test_get_card_not_found(self, authenticated_client):
        """Getting a card when none exists should return 404."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        response = await authenticated_client.get(f"/accounts/{account_id}/card")
        assert response.status_code == 404
        assert "No card found" in response.json()["detail"]


class TestCardEncryption:
    """Tests that card data is encrypted at rest in the database."""

    async def test_card_number_encrypted_in_db(self, authenticated_client, db_session):
        """The full card number stored in DB should be encrypted, not plaintext."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        card_response = await authenticated_client.post(f"/accounts/{account_id}/card")
        card_id = card_response.json()["id"]
        last_four = card_response.json()["card_number_last_four"]

        # Read the card directly from the database
        result = await db_session.execute(
            select(Card).where(Card.id == uuid.UUID(card_id))
        )
        card = result.scalar_one()

        # The encrypted field should NOT be readable as a plain card number
        assert isinstance(card.card_number_encrypted, bytes)
        raw_bytes = card.card_number_encrypted
        assert not raw_bytes.decode("utf-8", errors="ignore").isdigit()

        # But decrypting it should give a valid 16-digit card number
        decrypted = decrypt_value(raw_bytes)
        assert len(decrypted) == 16
        assert decrypted.isdigit()
        assert decrypted[-4:] == last_four

    async def test_cvv_encrypted_in_db(self, authenticated_client, db_session):
        """The CVV stored in DB should be encrypted, not plaintext."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        card_response = await authenticated_client.post(f"/accounts/{account_id}/card")
        card_id = card_response.json()["id"]

        result = await db_session.execute(
            select(Card).where(Card.id == uuid.UUID(card_id))
        )
        card = result.scalar_one()

        assert isinstance(card.cvv_encrypted, bytes)
        decrypted = decrypt_value(card.cvv_encrypted)
        assert len(decrypted) == 3
        assert decrypted.isdigit()


class TestDebitCardPurchase:
    """Tests for card-linked debit transactions.

    In the debit card model, the card is a payment instrument — purchases
    debit the linked account directly. The card_id on the transaction
    records which card was used.
    """

    async def test_purchase_with_card(self, authenticated_client):
        """A debit with card_id should record the card on the transaction."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        # Fund the account
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 10000},
        )

        # Issue a card
        card = await authenticated_client.post(f"/accounts/{account_id}/card")
        card_id = card.json()["id"]

        # Make a purchase with the card
        response = await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={
                "type": "debit",
                "amount_cents": 3000,
                "description": "Coffee shop",
                "card_id": card_id,
            },
        )
        assert response.status_code == 201
        txn = response.json()
        assert txn["card_id"] == card_id
        assert txn["status"] == "approved"
        assert txn["amount_cents"] == 3000

        # Balance should be reduced
        balance = await authenticated_client.get(f"/accounts/{account_id}/balance")
        assert balance.json()["cached_balance_cents"] == 7000

    async def test_purchase_without_card(self, authenticated_client):
        """A debit without card_id should have null card_id (cash/ACH)."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 5000},
        )

        response = await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "debit", "amount_cents": 1000},
        )
        assert response.status_code == 201
        assert response.json()["card_id"] is None

    async def test_card_from_wrong_account_rejected(self, authenticated_client):
        """Cannot use a card from a different account."""
        acct_a = await authenticated_client.post("/accounts", json={})
        acct_b = await authenticated_client.post("/accounts", json={})
        account_a_id = acct_a.json()["id"]
        account_b_id = acct_b.json()["id"]

        # Fund account B
        await authenticated_client.post(
            f"/accounts/{account_b_id}/transactions",
            json={"type": "credit", "amount_cents": 10000},
        )

        # Issue card on account A
        card = await authenticated_client.post(f"/accounts/{account_a_id}/card")
        card_a_id = card.json()["id"]

        # Try to use account A's card on account B
        response = await authenticated_client.post(
            f"/accounts/{account_b_id}/transactions",
            json={
                "type": "debit",
                "amount_cents": 1000,
                "card_id": card_a_id,
            },
        )
        assert response.status_code == 400
        assert "does not belong to this account" in response.json()["detail"]

    async def test_card_on_credit_rejected(self, authenticated_client):
        """Cannot use a card for deposit (credit) transactions."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        card = await authenticated_client.post(f"/accounts/{account_id}/card")
        card_id = card.json()["id"]

        response = await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={
                "type": "credit",
                "amount_cents": 5000,
                "card_id": card_id,
            },
        )
        assert response.status_code == 400
        assert "cannot be used for deposit" in response.json()["detail"].lower()

    async def test_nonexistent_card_rejected(self, authenticated_client):
        """Using a nonexistent card_id should return 404."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={"type": "credit", "amount_cents": 5000},
        )

        response = await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={
                "type": "debit",
                "amount_cents": 1000,
                "card_id": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 404
        assert "Card not found" in response.json()["detail"]

    async def test_declined_card_purchase_records_card_id(self, authenticated_client):
        """A declined card purchase should still record the card_id in the audit trail."""
        account = await authenticated_client.post("/accounts", json={})
        account_id = account.json()["id"]

        card = await authenticated_client.post(f"/accounts/{account_id}/card")
        card_id = card.json()["id"]

        # Try to purchase with zero balance
        await authenticated_client.post(
            f"/accounts/{account_id}/transactions",
            json={
                "type": "debit",
                "amount_cents": 5000,
                "card_id": card_id,
            },
        )

        # Check declined transaction has card_id
        txns = await authenticated_client.get(
            f"/accounts/{account_id}/transactions?status=declined"
        )
        assert len(txns.json()) == 1
        assert txns.json()[0]["card_id"] == card_id


class TestCardOwnership:
    """Tests that users can only access their own cards."""

    async def test_cannot_issue_card_for_other_users_account(self, client):
        """User B should not be able to issue a card on User A's account."""
        signup_a = await client.post(
            "/auth/signup",
            json={
                "email": "card_owner@example.com",
                "password": "StrongPass99!",
                "first_name": "Card",
                "last_name": "Owner",
            },
        )
        headers_a = {"Authorization": f"Bearer {signup_a.json()['token']}"}
        acct_a = await client.post("/accounts", json={}, headers=headers_a)
        account_a_id = acct_a.json()["id"]

        signup_b = await client.post(
            "/auth/signup",
            json={
                "email": "card_thief@example.com",
                "password": "StrongPass99!",
                "first_name": "Card",
                "last_name": "Thief",
            },
        )
        headers_b = {"Authorization": f"Bearer {signup_b.json()['token']}"}

        response = await client.post(
            f"/accounts/{account_a_id}/card", headers=headers_b
        )
        assert response.status_code == 403

    async def test_cannot_view_other_users_card(self, client):
        """User B should not be able to view User A's card."""
        signup_a = await client.post(
            "/auth/signup",
            json={
                "email": "card_viewer_a@example.com",
                "password": "StrongPass99!",
                "first_name": "Viewer",
                "last_name": "A",
            },
        )
        headers_a = {"Authorization": f"Bearer {signup_a.json()['token']}"}
        acct_a = await client.post("/accounts", json={}, headers=headers_a)
        account_a_id = acct_a.json()["id"]
        await client.post(f"/accounts/{account_a_id}/card", headers=headers_a)

        signup_b = await client.post(
            "/auth/signup",
            json={
                "email": "card_viewer_b@example.com",
                "password": "StrongPass99!",
                "first_name": "Viewer",
                "last_name": "B",
            },
        )
        headers_b = {"Authorization": f"Bearer {signup_b.json()['token']}"}

        response = await client.get(
            f"/accounts/{account_a_id}/card", headers=headers_b
        )
        assert response.status_code == 403


class TestAdminBlockedFromCards:
    """Tests that admins cannot issue or view cards (member-only endpoints)."""

    async def test_admin_cannot_issue_card(self, admin_client):
        """Admins should get 403 on card issuance endpoint."""
        fake_id = str(uuid.uuid4())
        response = await admin_client.post(f"/accounts/{fake_id}/card")
        assert response.status_code == 403

    async def test_admin_cannot_view_card(self, admin_client):
        """Admins should get 403 on card retrieval endpoint."""
        fake_id = str(uuid.uuid4())
        response = await admin_client.get(f"/accounts/{fake_id}/card")
        assert response.status_code == 403
