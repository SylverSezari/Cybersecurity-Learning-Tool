from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, TypedDict

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash

from config import settings

# Set up password hashing and bearer-token extraction for authentication.
_password_hash = PasswordHash.recommended()
# Handle missing credentials here so the dependency can return a consistent error.
_bearer_scheme = HTTPBearer(auto_error=False)


# The authenticated identity returned by the token-checking dependency.
class Principal(TypedDict):
    role: Literal["admin", "user"]
    account_id: int | None


# Convert a plain-text password into a hash suitable for storing in the database.
def hash_password(password: str) -> str:
    return _password_hash.hash(password)


# Check a plain-text password against the hash stored for an account.
def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


# Create a signed JWT containing the subject, role, and a two-hour expiration time.
def create_access_token(*, subject: str, role: Literal["admin", "user"]) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=120)
    return jwt.encode(
        {"sub": subject, "role": role, "exp": expires_at},
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )


# Decode a signed access token and return the authenticated principal.
def _principal_from_token(token: str | None) -> Principal:
    # Use the same response for missing, malformed, invalid, and expired tokens.
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise unauthorized

    # Decode verifies the token signature and expiration using the configured key and algorithm. Invalid JWTs are reported as an authentication failure.
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
        )
    except jwt.InvalidTokenError:
        raise unauthorized from None

    subject = payload.get("sub")
    role = payload.get("role")
    # Both claims are needed to identify an allowed admin or user principal.
    if not isinstance(subject, str):
        raise unauthorized

    # The admin token must identify the configured admin account.
    if role == "admin" and subject == settings.admin:
        return {"role": "admin", "account_id": None}

    # User subjects contain their positive database account ID as a string.
    if role == "user":
        try:
            account_id = int(subject)
        except ValueError:
            raise unauthorized from None
        if account_id > 0:
            return {"role": "user", "account_id": account_id}

    # Reject unrecognized roles, mismatched admin subjects, and invalid user IDs.
    raise unauthorized


# Validate bearer tokens for API requests.
async def get_current_principal(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> Principal:
    return _principal_from_token(
        credentials.credentials if credentials is not None else None
    )


# Browser navigations cannot send Authorization headers, so accept the login cookie here.
async def get_page_principal(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> Principal:
    token = (
        credentials.credentials
        if credentials is not None
        else request.cookies.get("access_token")
    )
    return _principal_from_token(token)


async def get_optional_page_principal(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> Principal | None:
    # Allow public page handlers to redirect missing or stale sessions to login.
    token = (
        credentials.credentials
        if credentials is not None
        else request.cookies.get("access_token")
    )
    if token is None:
        return None

    try:
        return _principal_from_token(token)
    except HTTPException:
        return None


def require_admin(principal: Principal) -> None:
    # Raise a forbidden response when a route is called by a learner account.
    if principal["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
