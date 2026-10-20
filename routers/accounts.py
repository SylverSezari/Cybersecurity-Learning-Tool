import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

import models
from config import settings
from database import get_db
from schemas import AccountCreate, AccountLogin, AccountResponse, Token
from security import (
    Principal,
    create_access_token,
    get_current_principal,
    hash_password,
    require_admin,
    verify_password,
)

router = APIRouter()

# All available http requests to accounts are here


## Get all accounts
@router.get("", response_model=list[AccountResponse])
async def get_all_accounts(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_admin(principal)
    result = await db.execute(select(models.Account))

    accounts = result.scalars().all()
    return accounts


@router.get("/session")
async def validate_session(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    if principal["role"] == "user":
        result = await db.execute(
            select(models.Account.id).where(
                models.Account.id == principal["account_id"]
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account no longer exists",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return {"valid": True}


## Get a single account
@router.get("/{account_id}", response_model=AccountResponse)
async def get_single_account(
    account_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    if principal["role"] != "admin" and principal["account_id"] != account_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )

    # check if account exists
    result = await db.execute(
        select(models.Account).where(models.Account.id == account_id)
    )

    account = result.scalars().first()

    if account:
        return account

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
    )


## Create an account
@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    account: AccountCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_admin(principal)

    # check if account with name exists already
    result = await db.execute(
        select(models.Account).where(
            func.lower(models.Account.username) == account.username.lower()
        )
    )
    existing_account = result.scalars().first()
    if existing_account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account with this username exists already",
        )

    password_hash = await run_in_threadpool(hash_password, account.password)
    new_account = models.Account(
        username=account.username,
        password_hash=password_hash,
    )

    db.add(new_account)
    await db.commit()
    await db.refresh(new_account)
    return new_account


@router.post("/token", response_model=Token)
async def login(
    credentials: AccountLogin,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if credentials.username == settings.admin and hmac.compare_digest(
        credentials.password.encode("utf-8"),
        settings.admin_password.get_secret_value().encode("utf-8"),
    ):
        access_token = create_access_token(
            subject=settings.admin,
            role="admin",
        )
        return Token(access_token=access_token, token_type="bearer")

    result = await db.execute(
        select(models.Account).where(
            func.lower(models.Account.username) == credentials.username.lower()
        )
    )
    account = result.scalars().first()
    if account is None or not await run_in_threadpool(
        verify_password,
        credentials.password,
        account.password_hash if account is not None else "",
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    access_token = create_access_token(
        subject=str(account.id),
        role="user",
    )
    return Token(access_token=access_token, token_type="bearer")


## delete account
@router.delete("/delete/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    
    require_admin(principal)
    
    # Check if account exists
    result = await db.execute(
        select(models.Account).where(models.Account.id == account_id)
    )

    account = result.scalars().first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
        
    # delete account
    await db.delete(account)
    await db.commit()