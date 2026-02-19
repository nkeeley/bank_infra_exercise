"""
Statements router — monthly account statement generation.

Endpoints:
  GET /accounts/{account_id}/statements?year=YYYY&month=MM

Generates a statement for the specified account and month. The response
includes aggregate data (opening/closing balance, totals) at the top,
followed by the full list of transactions for the period.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_account_holder
from app.models.account_holder import AccountHolder
from app.schemas.statement import StatementResponse
from app.services import statement_service

router = APIRouter()


@router.get(
    "/{account_id}/statements",
    response_model=StatementResponse,
    summary="Get monthly account statement",
)
async def get_statement(
    account_id: uuid.UUID,
    year: int = Query(..., ge=2000, le=2100, description="Statement year"),
    month: int = Query(..., ge=1, le=12, description="Statement month (1-12)"),
    account_holder: AccountHolder = Depends(get_current_account_holder),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a monthly statement for an account.

    The statement includes:
    - **Opening balance**: Account balance at the start of the month
    - **Closing balance**: Account balance at the end of the month
    - **Total credits/debits**: Sum of all credits and debits for the month
    - **Transaction count**: Number of transactions in the period
    - **Transactions**: Full list of every transaction, ordered chronologically

    Query parameters `year` and `month` are required.
    """
    return await statement_service.generate_statement(
        db=db,
        account_id=account_id,
        account_holder_id=account_holder.id,
        year=year,
        month=month,
    )
