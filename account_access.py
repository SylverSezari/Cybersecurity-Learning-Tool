"""Shared access checks for endpoints that require a learner account."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from security import Principal


async def require_user_account(db: AsyncSession, principal: Principal) -> models.Account:
    """Return the learner's live account; reject admins and deleted accounts."""
    account_id = principal["account_id"]
    if principal["role"] != "user" or account_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account required",
        )

    # A token can remain valid after its account has been deleted, so verify it.
    result = await db.execute(
        select(models.Account).where(models.Account.id == account_id)
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account no longer exists",
        )
    return account
