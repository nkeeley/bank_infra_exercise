"""
Custom exception classes and FastAPI exception handlers.

Why custom exceptions?
  FastAPI's default HTTPException works, but custom exceptions let the
  service layer raise domain-specific errors (like InsufficientFundsError)
  without importing HTTP concepts. The router/handler layer then translates
  these into proper HTTP responses.

  This separation means:
    - Service code is testable without HTTP
    - Error responses are consistent across all endpoints
    - Adding new error types is straightforward

Exception hierarchy:
    BankAPIError (base)
    ├── InsufficientFundsError   — debit/transfer when balance too low
    ├── AccountNotFoundError     — requested account doesn't exist
    ├── UnauthorizedAccessError  — user trying to access another's resource
    └── DuplicateCardError       — issuing a second card for an account
"""

import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


# ---------------------------------------------------------------------------
# Base exception
# ---------------------------------------------------------------------------

class BankAPIError(Exception):
    """Base exception for all Bank API domain errors."""

    def __init__(self, detail: str = "An error occurred"):
        self.detail = detail
        super().__init__(self.detail)


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------

class InsufficientFundsError(BankAPIError):
    """
    Raised when a debit or transfer would cause a negative balance.

    Attributes:
        account_id: The account that lacks sufficient funds.
        requested_cents: The amount the user tried to debit.
        available_cents: The current balance of the account.
    """

    def __init__(
        self,
        account_id: uuid.UUID,
        requested_cents: int,
        available_cents: int,
    ):
        self.account_id = account_id
        self.requested_cents = requested_cents
        self.available_cents = available_cents
        super().__init__(
            f"Insufficient funds: requested {requested_cents} cents, "
            f"available {available_cents} cents"
        )


class AccountNotFoundError(BankAPIError):
    """Raised when a requested account does not exist."""

    def __init__(self, account_id: uuid.UUID):
        self.account_id = account_id
        super().__init__(f"Account {account_id} not found")


class UnauthorizedAccessError(BankAPIError):
    """Raised when a user attempts to access a resource they don't own."""

    def __init__(self, detail: str = "You do not have access to this resource"):
        super().__init__(detail)


class DuplicateCardError(BankAPIError):
    """Raised when attempting to issue a card for an account that already has one."""

    def __init__(self, account_id: uuid.UUID):
        self.account_id = account_id
        super().__init__(f"Account {account_id} already has a card")


class DuplicateEmailError(BankAPIError):
    """Raised when attempting to register with an email that's already in use."""

    def __init__(self, email: str):
        self.email = email
        super().__init__(f"Email {email} is already registered")


class InvalidCredentialsError(BankAPIError):
    """Raised when login credentials are incorrect."""

    def __init__(self):
        super().__init__("Invalid email or password")


# ---------------------------------------------------------------------------
# FastAPI exception handlers
# ---------------------------------------------------------------------------

def register_exception_handlers(app: FastAPI) -> None:
    """
    Register custom exception handlers with the FastAPI application.

    Each handler maps a domain exception to an HTTP status code and
    consistent JSON response format: {"detail": "error message"}

    This is called once during app startup in main.py.
    """

    @app.exception_handler(InsufficientFundsError)
    async def insufficient_funds_handler(
        request: Request, exc: InsufficientFundsError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,  # Unprocessable Entity — the request was valid but business rules reject it
            content={
                "detail": exc.detail,
                "error_type": "insufficient_funds",
                "requested_cents": exc.requested_cents,
                "available_cents": exc.available_cents,
            },
        )

    @app.exception_handler(AccountNotFoundError)
    async def account_not_found_handler(
        request: Request, exc: AccountNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": exc.detail, "error_type": "account_not_found"},
        )

    @app.exception_handler(UnauthorizedAccessError)
    async def unauthorized_access_handler(
        request: Request, exc: UnauthorizedAccessError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"detail": exc.detail, "error_type": "unauthorized_access"},
        )

    @app.exception_handler(DuplicateCardError)
    async def duplicate_card_handler(
        request: Request, exc: DuplicateCardError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,  # Conflict — the resource already exists
            content={"detail": exc.detail, "error_type": "duplicate_card"},
        )

    @app.exception_handler(DuplicateEmailError)
    async def duplicate_email_handler(
        request: Request, exc: DuplicateEmailError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": exc.detail, "error_type": "duplicate_email"},
        )

    @app.exception_handler(InvalidCredentialsError)
    async def invalid_credentials_handler(
        request: Request, exc: InvalidCredentialsError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"detail": exc.detail, "error_type": "invalid_credentials"},
        )
