"""Expose authenticated account management, sign-in, and bulk CSV import routes."""

import csv
import hmac
import io
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from account_helpers import generate_password, random_klasse
import models
from config import settings
from database import get_db
from schemas import AccountCreate, AccountLogin, AccountPut, AccountResponse, Token
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


def _clean_name(value: str) -> str:
    """Keep only letters when building a username from a student's name."""
    return "".join(character for character in value.strip() if character.isalpha())


def _available_username(
    first_name: str,
    family_name: str,
    used_usernames: set[str],
    row_number: int,
) -> str:
    """Use a progressively longer first-name prefix until a username is unique."""
    first_name = _clean_name(first_name)
    family_name = _clean_name(family_name)
    if not first_name or not family_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"CSV-Zeile {row_number}: Vorname und Name müssen Buchstaben enthalten.",
        )

    base = first_name.lower() + family_name.lower()
    if len(base) > 20:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"CSV-Zeile {row_number}: Der erzeugte Benutzername darf höchstens 20 Zeichen lang sein.",
        )

    for prefix_length in range(1, len(first_name) + 1):
        candidate = first_name[:prefix_length].lower() + family_name.lower()
        if candidate.casefold() not in used_usernames:
            used_usernames.add(candidate.casefold())
            return candidate

    suffix = 2
    while True:
        suffix_text = str(suffix)
        candidate = f"{base[:20 - len(suffix_text)]}{suffix_text}"
        if candidate.casefold() not in used_usernames:
            used_usernames.add(candidate.casefold())
            return candidate
        suffix += 1


def _parse_student_csv(contents: str) -> list[dict[str, str]]:
    """Validate the semicolon-separated student export before creating accounts."""
    try:
        reader = csv.DictReader(io.StringIO(contents), delimiter=";")
        if reader.fieldnames is None or not {
            "Name",
            "Vorname",
            "Klasse",
        }.issubset(reader.fieldnames):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Die CSV-Datei muss die Spalten Name, Vorname und Klasse enthalten.",
            )

        students = []
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"CSV-Zeile {row_number}: Unerwartet viele Spalten.",
                )
            if not any(
                (row.get(fieldname) or "").strip()
                for fieldname in reader.fieldnames or []
            ):
                continue
            name = (row.get("Name") or "").strip()
            first_name = (row.get("Vorname") or "").strip()
            klasse = (row.get("Klasse") or "").strip()
            if not name or not first_name or not klasse:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"CSV-Zeile {row_number}: Name, Vorname und Klasse dürfen nicht leer sein.",
                )
            students.append(
                {"name": name, "first_name": first_name, "klasse": klasse}
            )
    except csv.Error as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Die CSV-Datei ist ungültig: {error}",
        ) from error

    if not students:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Die CSV-Datei enthält keine Schülerkonten.",
        )
    return students


## Get all accounts
@router.get("", response_model=list[AccountResponse])
async def get_all_accounts(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Return public account fields to administrators only.
    require_admin(principal)
    result = await db.execute(select(models.Account))

    accounts = result.scalars().all()
    return accounts


@router.get("/session")
async def validate_session(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Confirm that the token is valid and its learner account still exists.
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

    return {"valid": True, "role": principal["role"]}


@router.post("/import-csv")
async def import_accounts_csv(
    file: Annotated[UploadFile, File()],
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    require_admin(principal)
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Bitte eine CSV-Datei auswählen.",
        )

    contents = await file.read(2_000_001)
    if len(contents) > 2_000_000:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Die CSV-Datei darf höchstens 2 MB groß sein.",
        )
    try:
        csv_text = contents.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Die CSV-Datei muss UTF-8-kodiert sein.",
        ) from error

    students = _parse_student_csv(csv_text)
    result = await db.execute(select(models.Account.username))
    used_usernames = {username.casefold() for username in result.scalars().all()}
    accounts_to_create = []
    for row_number, student in enumerate(students, start=2):
        username = _available_username(
            student["first_name"],
            student["name"],
            used_usernames,
            row_number,
        )
        password = generate_password()
        accounts_to_create.append(
            {
                "username": username,
                "password": password,
                "klasse": student["klasse"],
                "password_hash": await run_in_threadpool(hash_password, password),
            }
        )

    db.add_all(
        [
            models.Account(
                username=account["username"],
                password_hash=account["password_hash"],
                klasse=account["klasse"],
            )
            for account in accounts_to_create
        ]
    )
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Beim Import ist ein Benutzername-Konflikt aufgetreten. Bitte erneut versuchen.",
        ) from error

    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Benutzername", "Passwort", "Klasse"])
    writer.writerows(
        (account["username"], account["password"], account["klasse"])
        for account in accounts_to_create
    )
    return Response(
        content=output.getvalue(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="schueler-zugangsdaten.txt"',
            "X-Imported-Count": str(len(accounts_to_create)),
        },
    )


## Get a single account
@router.get("/{account_id}", response_model=AccountResponse)
async def get_single_account(
    account_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Return one account to an administrator or to that account's owner.
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
    # Create a learner after checking username uniqueness and hashing its password.
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
        klasse=account.klasse or random_klasse(),
    )

    db.add(new_account)
    await db.commit()
    await db.refresh(new_account)
    return new_account


@router.put("/update/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: int,
    update_data: AccountPut,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Update an account's username and/or replace its password hash.
    require_admin(principal)

    result = await db.execute(
        select(models.Account).where(models.Account.id == account_id)
    )
    account = result.scalars().first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )

    if update_data.username is not None:
        result = await db.execute(
            select(models.Account).where(
                func.lower(models.Account.username) == update_data.username.lower(),
                models.Account.id != account_id,
            )
        )
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Account with this username already exists",
            )
        account.username = update_data.username

    if update_data.password is not None:
        account.password_hash = await run_in_threadpool(
            hash_password, update_data.password
        )

    if update_data.klasse is not None:
        account.klasse = update_data.klasse

    await db.commit()
    await db.refresh(account)
    return account


@router.post("/token", response_model=Token)
async def login(
    credentials: AccountLogin,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
    response: Response,
):
    # Authenticate the configured administrator or a stored learner account.
    if credentials.username == settings.admin and hmac.compare_digest(
        credentials.password.encode("utf-8"),
        settings.admin_password.get_secret_value().encode("utf-8"),
    ):
        access_token = create_access_token(
            subject=settings.admin,
            role="admin",
        )
        _set_access_cookie(response, request, access_token)
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
    _set_access_cookie(response, request, access_token)
    return Token(access_token=access_token, token_type="bearer")


def _set_access_cookie(response: Response, request: Request, token: str) -> None:
    # Set the browser-session cookie with transport and script-access protections.
    response.set_cookie(
        "access_token",
        token,
        max_age=120 * 60,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )


## delete account
@router.delete("/delete/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Delete an account and its recorded completion rows.

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

    await db.execute(
        delete(models.ExerciseCompletion).where(
            models.ExerciseCompletion.account_id == account_id
        )
    )

    # delete account
    await db.delete(account)
    await db.commit()
