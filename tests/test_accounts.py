"""
Tests for account management endpoints and role-based access control.

These tests verify:
  - Members can create, list, and view their own accounts
  - Members CANNOT access another user's accounts (403)
  - Admins can view ALL accounts and balances (read-only)
  - Admins CANNOT access member banking endpoints (403)
  - New accounts start with zero balance
  - Invalid account types are rejected
"""

import uuid

import pytest


# ---------------------------------------------------------------------------
# Member: Account Creation
# ---------------------------------------------------------------------------

class TestAccountCreation:
    """Tests for POST /accounts (member endpoint)."""

    async def test_create_checking_account(self, authenticated_client):
        """Members can create a checking account."""
        response = await authenticated_client.post(
            "/accounts",
            json={"account_type": "checking"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["account_type"] == "checking"
        assert data["cached_balance_cents"] == 0
        assert data["currency"] == "USD"
        assert data["is_active"] is True
        assert len(data["account_number"]) == 10

    async def test_create_savings_account(self, authenticated_client):
        """Members can create a savings account."""
        response = await authenticated_client.post(
            "/accounts",
            json={"account_type": "savings"},
        )
        assert response.status_code == 201
        assert response.json()["account_type"] == "savings"

    async def test_create_default_checking(self, authenticated_client):
        """Default account type should be 'checking' when not specified."""
        response = await authenticated_client.post("/accounts", json={})
        assert response.status_code == 201
        assert response.json()["account_type"] == "checking"

    async def test_create_invalid_account_type(self, authenticated_client):
        """Invalid account types should be rejected (422)."""
        response = await authenticated_client.post(
            "/accounts",
            json={"account_type": "investment"},
        )
        assert response.status_code == 422

    async def test_create_multiple_accounts(self, authenticated_client):
        """A member can create multiple accounts."""
        await authenticated_client.post("/accounts", json={"account_type": "checking"})
        await authenticated_client.post("/accounts", json={"account_type": "savings"})

        response = await authenticated_client.get("/accounts")
        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_new_account_balance_is_zero(self, authenticated_client):
        """A newly created account must have a zero balance."""
        create_response = await authenticated_client.post("/accounts", json={})
        account_id = create_response.json()["id"]

        balance_response = await authenticated_client.get(
            f"/accounts/{account_id}/balance"
        )
        assert balance_response.status_code == 200
        data = balance_response.json()
        assert data["cached_balance_cents"] == 0
        assert data["computed_balance_cents"] == 0
        assert data["match"] is True


# ---------------------------------------------------------------------------
# Member: Account Retrieval
# ---------------------------------------------------------------------------

class TestAccountRetrieval:
    """Tests for GET /accounts and GET /accounts/{id}."""

    async def test_list_accounts_empty(self, authenticated_client):
        """A new user should have no accounts."""
        response = await authenticated_client.get("/accounts")
        assert response.status_code == 200
        assert response.json() == []

    async def test_get_account_by_id(self, authenticated_client):
        """A member can get their own account by ID."""
        create_response = await authenticated_client.post("/accounts", json={})
        account_id = create_response.json()["id"]

        response = await authenticated_client.get(f"/accounts/{account_id}")
        assert response.status_code == 200
        assert response.json()["id"] == account_id

    async def test_get_nonexistent_account(self, authenticated_client):
        """Requesting a non-existent account ID should return 404."""
        fake_id = str(uuid.uuid4())
        response = await authenticated_client.get(f"/accounts/{fake_id}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Member: Ownership Enforcement (Cross-User Access Denied)
# ---------------------------------------------------------------------------

class TestOwnershipEnforcement:
    """Tests that members cannot access other users' accounts."""

    async def test_cannot_view_other_users_account(self, client):
        """User A should NOT be able to view User B's account (403)."""
        # Sign up User A and create an account
        signup_a = await client.post(
            "/auth/signup",
            json={
                "email": "usera@example.com",
                "password": "StrongPass99!",
                "first_name": "User",
                "last_name": "A",
            },
        )
        token_a = signup_a.json()["token"]
        create_response = await client.post(
            "/accounts",
            json={},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        account_a_id = create_response.json()["id"]

        # Sign up User B
        signup_b = await client.post(
            "/auth/signup",
            json={
                "email": "userb@example.com",
                "password": "StrongPass99!",
                "first_name": "User",
                "last_name": "B",
            },
        )
        token_b = signup_b.json()["token"]

        # User B tries to access User A's account
        response = await client.get(
            f"/accounts/{account_a_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert response.status_code == 403

    async def test_cannot_view_other_users_balance(self, client):
        """User A should NOT be able to check User B's balance (403)."""
        # Sign up User A and create an account
        signup_a = await client.post(
            "/auth/signup",
            json={
                "email": "balA@example.com",
                "password": "StrongPass99!",
                "first_name": "User",
                "last_name": "A",
            },
        )
        token_a = signup_a.json()["token"]
        create_response = await client.post(
            "/accounts",
            json={},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        account_a_id = create_response.json()["id"]

        # Sign up User B
        signup_b = await client.post(
            "/auth/signup",
            json={
                "email": "balB@example.com",
                "password": "StrongPass99!",
                "first_name": "User",
                "last_name": "B",
            },
        )
        token_b = signup_b.json()["token"]

        # User B tries to check User A's balance
        response = await client.get(
            f"/accounts/{account_a_id}/balance",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert response.status_code == 403

    async def test_list_only_shows_own_accounts(self, client):
        """GET /accounts should only return the current user's accounts."""
        # Sign up User A and create 2 accounts
        signup_a = await client.post(
            "/auth/signup",
            json={
                "email": "listA@example.com",
                "password": "StrongPass99!",
                "first_name": "User",
                "last_name": "A",
            },
        )
        token_a = signup_a.json()["token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}
        await client.post("/accounts", json={}, headers=headers_a)
        await client.post("/accounts", json={}, headers=headers_a)

        # Sign up User B and create 1 account
        signup_b = await client.post(
            "/auth/signup",
            json={
                "email": "listB@example.com",
                "password": "StrongPass99!",
                "first_name": "User",
                "last_name": "B",
            },
        )
        token_b = signup_b.json()["token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}
        await client.post("/accounts", json={}, headers=headers_b)

        # User A sees 2 accounts, User B sees 1
        response_a = await client.get("/accounts", headers=headers_a)
        assert len(response_a.json()) == 2

        response_b = await client.get("/accounts", headers=headers_b)
        assert len(response_b.json()) == 1


# ---------------------------------------------------------------------------
# Admin: Read-Only Access to All Accounts
# ---------------------------------------------------------------------------

class TestAdminReadOnly:
    """Tests that admins can view all accounts but not modify them."""

    async def test_admin_can_list_all_accounts(self, admin_client, client):
        """Admin should see ALL accounts across all users."""
        # Create a member account
        signup = await client.post(
            "/auth/signup",
            json={
                "email": "member_for_admin@example.com",
                "password": "StrongPass99!",
                "first_name": "Member",
                "last_name": "ForAdmin",
            },
        )
        member_token = signup.json()["token"]
        await client.post(
            "/accounts",
            json={},
            headers={"Authorization": f"Bearer {member_token}"},
        )

        # Admin lists all accounts
        response = await admin_client.get("/admin/accounts")
        assert response.status_code == 200
        accounts = response.json()
        assert len(accounts) >= 1

    async def test_admin_can_view_any_account(self, admin_client, client):
        """Admin should be able to view any specific account."""
        signup = await client.post(
            "/auth/signup",
            json={
                "email": "viewable@example.com",
                "password": "StrongPass99!",
                "first_name": "View",
                "last_name": "Able",
            },
        )
        member_token = signup.json()["token"]
        create_response = await client.post(
            "/accounts",
            json={},
            headers={"Authorization": f"Bearer {member_token}"},
        )
        account_id = create_response.json()["id"]

        # Admin views the member's account
        response = await admin_client.get(f"/admin/accounts/{account_id}")
        assert response.status_code == 200
        assert response.json()["id"] == account_id

    async def test_admin_can_view_any_balance(self, admin_client, client):
        """Admin should be able to check any account's balance."""
        signup = await client.post(
            "/auth/signup",
            json={
                "email": "balance_check@example.com",
                "password": "StrongPass99!",
                "first_name": "Balance",
                "last_name": "Check",
            },
        )
        member_token = signup.json()["token"]
        create_response = await client.post(
            "/accounts",
            json={},
            headers={"Authorization": f"Bearer {member_token}"},
        )
        account_id = create_response.json()["id"]

        response = await admin_client.get(f"/admin/accounts/{account_id}/balance")
        assert response.status_code == 200
        data = response.json()
        assert data["cached_balance_cents"] == 0
        assert data["match"] is True


# ---------------------------------------------------------------------------
# Admin: Blocked from Member Banking Endpoints
# ---------------------------------------------------------------------------

class TestAdminBlockedFromMemberEndpoints:
    """Tests that admins CANNOT use member banking endpoints.

    Admins are blocked by the get_current_account_holder dependency,
    which checks user_type and returns 403 for ADMIN users. This
    prevents admins from creating accounts, initiating transfers,
    or performing any financial operations.
    """

    async def test_admin_cannot_create_account(self, admin_client):
        """Admins should NOT be able to create bank accounts."""
        response = await admin_client.post(
            "/accounts",
            json={"account_type": "checking"},
        )
        assert response.status_code == 403
        assert "Admin accounts cannot access member banking endpoints" in response.json()["detail"]

    async def test_admin_cannot_list_own_accounts(self, admin_client):
        """Admins should NOT be able to use the member account list endpoint."""
        response = await admin_client.get("/accounts")
        assert response.status_code == 403

    async def test_admin_cannot_view_account_via_member_endpoint(self, admin_client):
        """Admins should NOT be able to use the member account detail endpoint."""
        fake_id = str(uuid.uuid4())
        response = await admin_client.get(f"/accounts/{fake_id}")
        assert response.status_code == 403

    async def test_admin_cannot_check_balance_via_member_endpoint(self, admin_client):
        """Admins should NOT be able to use the member balance endpoint."""
        fake_id = str(uuid.uuid4())
        response = await admin_client.get(f"/accounts/{fake_id}/balance")
        assert response.status_code == 403

    async def test_admin_cannot_update_profile(self, admin_client):
        """Admins should NOT be able to use the member profile update endpoint."""
        response = await admin_client.patch(
            "/account-holders/me",
            json={"first_name": "Hacked"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Member: Blocked from Admin Endpoints
# ---------------------------------------------------------------------------

class TestMemberBlockedFromAdminEndpoints:
    """Tests that regular members cannot access admin endpoints."""

    async def test_member_cannot_list_all_accounts(self, authenticated_client):
        """Regular members should get 403 on admin list endpoint."""
        response = await authenticated_client.get("/admin/accounts")
        assert response.status_code == 403
        assert "Admin access required" in response.json()["detail"]

    async def test_member_cannot_view_admin_account_detail(self, authenticated_client):
        """Regular members should get 403 on admin account detail."""
        fake_id = str(uuid.uuid4())
        response = await authenticated_client.get(f"/admin/accounts/{fake_id}")
        assert response.status_code == 403

    async def test_member_cannot_view_admin_balance(self, authenticated_client):
        """Regular members should get 403 on admin balance endpoint."""
        fake_id = str(uuid.uuid4())
        response = await authenticated_client.get(f"/admin/accounts/{fake_id}/balance")
        assert response.status_code == 403

    async def test_unauthenticated_cannot_access_admin_endpoints(self, client):
        """Unauthenticated requests should get 401 on admin endpoints."""
        response = await client.get("/admin/accounts")
        assert response.status_code == 401
