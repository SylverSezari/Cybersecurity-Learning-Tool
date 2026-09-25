from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, TypedDict

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash

from config import settings

_password_hash = PasswordHash.recommended()
_bearer_scheme = HTTPBearer(auto_error=False)


class Principal(TypedDict):
    role: Literal["admin", "user"]
    account_id: int | None


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def create_access_token(
    *, subject: str, role: Literal["admin", "user"]
) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=30)
    return jwt.encode(
        {"sub": subject, "role": role, "exp": expires_at},
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )


async def get_current_principal(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> Principal:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
        )
    except jwt.InvalidTokenError:
        raise unauthorized from None

    subject = payload.get("sub")
    role = payload.get("role")
    if not isinstance(subject, str):
        raise unauthorized

    if role == "admin" and subject == settings.admin:
        return {"role": "admin", "account_id": None}

    if role == "user":
        try:
            account_id = int(subject)
        except ValueError:
            raise unauthorized from None
        if account_id > 0:
            return {"role": "user", "account_id": account_id}

    raise unauthorized