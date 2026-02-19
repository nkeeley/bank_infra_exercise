"""
Transfers router — atomic money transfers between accounts.

Endpoints:
  POST /transfers — Transfer money from one account to another

A transfer is an atomic operation that creates two linked transactions:
  1. A DEBIT from the source account
  2. A CREDIT to the destination account

Both transactions share a transfer_pair_id, making them trivially
linkable for auditing and reconciliation.

Only members can initiate transfers (admins are blocked from member
endpoints). The source account must belong to the authenticated user;
the destination can belong to anyone (enabling inter-user transfers).
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_account_holder
from app.models.account_holder import AccountHolder
from app.schemas.transaction import TransferRequest, TransferResponse, TransactionResponse
from app.services import transaction_service

router = APIRouter()


@router.post(
    "",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Transfer money between accounts",
)
async def create_transfer(
    request: TransferRequest,
    account_holder: AccountHolder = Depends(get_current_account_holder),
    db: AsyncSession = Depends(get_db),
):
    """
    Transfer money from one account to another.

    This is an atomic operation — either both the debit and credit succeed,
    or neither does. If the source account has insufficient funds, the
    transfer is rejected and a declined transaction is recorded.

    - **from_account_id**: Must belong to the authenticated user
    - **to_account_id**: Can belong to any user (enables inter-user transfers)
    - **amount_cents**: Positive integer in cents (e.g., $50.00 = 5000)
    - Cannot transfer to the same account
    """
    debit_txn, credit_txn, transfer_pair_id = await transaction_service.create_transfer(
        db=db,
        from_account_id=request.from_account_id,
        to_account_id=request.to_account_id,
        account_holder_id=account_holder.id,
        amount_cents=request.amount_cents,
        description=request.description,
    )

    return TransferResponse(
        transfer_pair_id=transfer_pair_id,
        debit_transaction=TransactionResponse.model_validate(debit_txn),
        credit_transaction=TransactionResponse.model_validate(credit_txn),
        amount_cents=request.amount_cents,
        from_account_id=request.from_account_id,
        to_account_id=request.to_account_id,
    )
