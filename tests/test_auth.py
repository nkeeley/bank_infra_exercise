"""
Tests for authentication endpoints (signup and login).

These tests verify:
  - Successful signup creates a user and returns a JWT
  - Duplicate email signup is rejected (409 Conflict)
  - Successful login returns a valid JWT
  - Wrong password is rejected (401 Unauthorized)
  - Non-existent email is rejected with the same error (anti-enumeration)
  - Short passwords are rejected (422 Validation Error)
  - Empty/missing fields are rejected
  - Profile updates cannot modify email (security boundary)
"""

import pytest


# ---------------------------------------------------------------------------
# Signup Tests
# ---------------------------------------------------------------------------

class TestSignup:
    """Tests for POST /auth/signup."""

    async def test_signup_success(self, client):
        """A valid signup should return 201 with user_id, email, and token."""
        response = await client.post(
            "/auth/signup",
            json={
                "email": "newuser@example.com",
                "password": "StrongPass99!",
                "first_name": "Jane",
                "last_name": "Doe",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["user_type"] == "member"
        assert "token" in data
        assert "user_id" in data

    async def test_signup_with_phone(self, client):
        """Signup should accept an optional phone number."""
        response = await client.post(
            "/auth/signup",
            json={
                "email": "phone@example.com",
                "password": "StrongPass99!",
                "first_name": "Jane",
                "last_name": "Doe",
                "phone": "+1-555-123-4567",
            },
        )
        assert response.status_code == 201

    async def test_signup_duplicate_email(self, client):
        """Signing up with an already-registered email should return 409."""
        signup_data = {
            "email": "duplicate@example.com",
            "password": "StrongPass99!",
            "first_name": "First",
            "last_name": "User",
        }
        # First signup succeeds
        response1 = await client.post("/auth/signup", json=signup_data)
        assert response1.status_code == 201

        # Second signup with same email fails
        response2 = await client.post("/auth/signup", json=signup_data)
        assert response2.status_code == 409
        assert "already registered" in response2.json()["detail"]

    async def test_signup_short_password(self, client):
        """Passwords shorter than 8 characters should be rejected."""
        response = await client.post(
            "/auth/signup",
            json={
                "email": "short@example.com",
                "password": "short",
                "first_name": "Test",
                "last_name": "User",
            },
        )
        assert response.status_code == 422  # Validation error

    async def test_signup_invalid_email(self, client):
        """Invalid email format should be rejected."""
        response = await client.post(
            "/auth/signup",
            json={
                "email": "not-an-email",
                "password": "StrongPass99!",
                "first_name": "Test",
                "last_name": "User",
            },
        )
        assert response.status_code == 422

    async def test_signup_missing_fields(self, client):
        """Missing required fields should return 422."""
        response = await client.post(
            "/auth/signup",
            json={"email": "missing@example.com"},
        )
        assert response.status_code == 422

    async def test_signup_empty_first_name(self, client):
        """Empty first_name should be rejected."""
        response = await client.post(
            "/auth/signup",
            json={
                "email": "empty@example.com",
                "password": "StrongPass99!",
                "first_name": "",
                "last_name": "User",
            },
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Login Tests
# ---------------------------------------------------------------------------

class TestLogin:
    """Tests for POST /auth/login."""

    async def test_login_success(self, client):
        """Login with correct credentials should return a token."""
        # First, create a user
        await client.post(
            "/auth/signup",
            json={
                "email": "login@example.com",
                "password": "CorrectPass123!",
                "first_name": "Test",
                "last_name": "User",
            },
        )

        # Then login
        response = await client.post(
            "/auth/login",
            json={
                "email": "login@example.com",
                "password": "CorrectPass123!",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client):
        """Login with wrong password should return 401."""
        await client.post(
            "/auth/signup",
            json={
                "email": "wrongpw@example.com",
                "password": "CorrectPass123!",
                "first_name": "Test",
                "last_name": "User",
            },
        )

        response = await client.post(
            "/auth/login",
            json={
                "email": "wrongpw@example.com",
                "password": "WrongPassword!",
            },
        )
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    async def test_login_nonexistent_email(self, client):
        """Login with an email that doesn't exist should return 401.

        Important: the error message must be identical to the wrong-password
        case to prevent user enumeration attacks.
        """
        response = await client.post(
            "/auth/login",
            json={
                "email": "nobody@example.com",
                "password": "SomePassword123!",
            },
        )
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    async def test_login_token_works_for_protected_endpoint(self, client):
        """The token from login should grant access to protected endpoints."""
        # Signup
        await client.post(
            "/auth/signup",
            json={
                "email": "protected@example.com",
                "password": "ValidPass123!",
                "first_name": "Protected",
                "last_name": "User",
            },
        )

        # Login
        login_response = await client.post(
            "/auth/login",
            json={
                "email": "protected@example.com",
                "password": "ValidPass123!",
            },
        )
        token = login_response.json()["token"]

        # Use token to access protected endpoint
        profile_response = await client.get(
            "/account-holders/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert profile_response.status_code == 200
        assert profile_response.json()["email"] == "protected@example.com"


# ---------------------------------------------------------------------------
# Token Validation Tests
# ---------------------------------------------------------------------------

class TestTokenValidation:
    """Tests for JWT token validation on protected endpoints."""

    async def test_no_token_returns_401(self, client):
        """Accessing a protected endpoint without a token should return 401."""
        response = await client.get("/account-holders/me")
        assert response.status_code == 401

    async def test_invalid_token_returns_401(self, client):
        """An invalid/forged token should return 401."""
        response = await client.get(
            "/account-holders/me",
            headers={"Authorization": "Bearer totally.fake.token"},
        )
        assert response.status_code == 401

    async def test_malformed_auth_header_returns_401(self, client):
        """A malformed Authorization header should return 401."""
        response = await client.get(
            "/account-holders/me",
            headers={"Authorization": "NotBearer sometoken"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Profile Security Tests
# ---------------------------------------------------------------------------

class TestProfileSecurity:
    """Tests that profile updates cannot modify security-sensitive fields."""

    async def test_cannot_change_email_via_profile_update(self, authenticated_client):
        """PATCH /account-holders/me should NOT allow changing email.

        Email is the authentication identifier — allowing it to be changed
        via a simple PATCH would be a security vulnerability. An attacker
        who steals a token could redirect the account to their own email.
        Email changes should require a dedicated flow with re-authentication.
        """
        # Try to change email via PATCH
        response = await authenticated_client.patch(
            "/account-holders/me",
            json={"email": "hacker@evil.com"},
        )

        # The request may succeed (200) because PATCH ignores unknown fields,
        # but the email must NOT have changed
        profile = await authenticated_client.get("/account-holders/me")
        assert profile.json()["email"] == "testuser@example.com"
        assert profile.json()["email"] != "hacker@evil.com"

    async def test_profile_update_only_changes_allowed_fields(self, authenticated_client):
        """PATCH should only update first_name, last_name, and phone."""
        response = await authenticated_client.patch(
            "/account-holders/me",
            json={
                "first_name": "Updated",
                "last_name": "Name",
                "phone": "+1-555-999-0000",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"
        assert data["last_name"] == "Name"
        assert data["phone"] == "+1-555-999-0000"
        # Email unchanged
        assert data["email"] == "testuser@example.com"
