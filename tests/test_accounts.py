from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

import models

# Test Accounts


## Test get_all_accounts
# Check that admins can list seeded accounts, while missing and regular-user tokens fail.


@pytest.mark.anyio
async def test_get_all_accounts_returns_accounts_to_admin(
	client: AsyncClient,
	admin_auth_headers: dict[str, str],
	test_account_factory: Callable[[str], Awaitable[dict]],
):
	# An admin can list all accounts, with password hashes omitted from responses.
	first_account = await test_account_factory("first_account")
	second_account = await test_account_factory("second_account")

	response = await client.get("/api/accounts", headers=admin_auth_headers)

	assert response.status_code == 200
	assert {account["id"] for account in response.json()} == {
		first_account["id"],
		second_account["id"],
	}
	assert all("password_hash" not in account for account in response.json())


@pytest.mark.anyio
async def test_get_all_accounts_rejects_missing_token(client: AsyncClient):
	# Listing accounts without a valid bearer token is unauthorized.
	response = await client.get("/api/accounts")

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid or expired authentication token"


@pytest.mark.anyio
async def test_get_all_accounts_rejects_regular_user(
	client: AsyncClient,
	user_auth_headers: dict[str, str],
):
	# A valid user token cannot access the admin-only account list.
	response = await client.get("/api/accounts", headers=user_auth_headers)

	assert response.status_code == 403
	assert response.json()["detail"] == "Admin privileges required"


## Test validate_session
# Check active admin/user sessions, missing credentials, and tokens for deleted accounts.


@pytest.mark.anyio
async def test_validate_session_accepts_admin_token(
	client: AsyncClient,
	admin_auth_headers: dict[str, str],
):
	# A valid admin token represents an active session.
	response = await client.get("/api/accounts/session", headers=admin_auth_headers)

	assert response.status_code == 200
	assert response.json() == {"valid": True}


@pytest.mark.anyio
async def test_validate_session_accepts_existing_user_token(
	client: AsyncClient,
	user_auth_headers: dict[str, str],
):
	# A user's session remains valid while the corresponding account exists.
	response = await client.get("/api/accounts/session", headers=user_auth_headers)

	assert response.status_code == 200
	assert response.json() == {"valid": True}


@pytest.mark.anyio
async def test_validate_session_rejects_missing_token(client: AsyncClient):
	# Session validation requires an authenticated request.
	response = await client.get("/api/accounts/session")

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid or expired authentication token"


@pytest.mark.anyio
async def test_validate_session_rejects_deleted_user_account(
	client: AsyncClient,
	db_session: AsyncSession,
	test_account_factory: Callable[[str], Awaitable[dict]],
):
	# A signed user token is invalidated when its account no longer exists.
	account = await test_account_factory("deleted_user")
	login_response = await client.post(
		"/api/accounts/token",
		json={"username": "deleted_user", "password": "testpassword123"},
	)
	assert login_response.status_code == 200, login_response.text
	user_headers = {
		"Authorization": f"Bearer {login_response.json()['access_token']}"
	}
	await db_session.execute(
		delete(models.Account).where(models.Account.id == account["id"])
	)
	await db_session.commit()

	response = await client.get("/api/accounts/session", headers=user_headers)

	assert response.status_code == 401
	assert response.json()["detail"] == "Account no longer exists"


## Test get_single_account
# Verify admin lookup, self-lookup, cross-account privacy, and not-found/auth responses.


@pytest.mark.anyio
async def test_get_single_account_returns_account_to_admin(
	client: AsyncClient,
	admin_auth_headers: dict[str, str],
	test_account_factory: Callable[[str], Awaitable[dict]],
):
	# An admin can retrieve any existing account by ID.
	account = await test_account_factory("admin_lookup_user")

	response = await client.get(
		f"/api/accounts/{account['id']}", headers=admin_auth_headers
	)

	assert response.status_code == 200
	assert response.json() == {"id": account["id"], "username": "admin_lookup_user"}


@pytest.mark.anyio
async def test_get_single_account_returns_own_account_to_user(
	client: AsyncClient,
	test_account_factory: Callable[[str], Awaitable[dict]],
):
	# A regular user can retrieve their own account details.
	account = await test_account_factory("self_lookup_user")
	login_response = await client.post(
		"/api/accounts/token",
		json={"username": "self_lookup_user", "password": "testpassword123"},
	)
	assert login_response.status_code == 200, login_response.text
	user_headers = {
		"Authorization": f"Bearer {login_response.json()['access_token']}"
	}

	response = await client.get(
		f"/api/accounts/{account['id']}", headers=user_headers
	)

	assert response.status_code == 200
	assert response.json()["id"] == account["id"]
	assert response.json()["username"] == "self_lookup_user"


@pytest.mark.anyio
async def test_get_single_account_hides_another_users_account(
	client: AsyncClient,
	test_account_factory: Callable[[str], Awaitable[dict]],
	user_auth_headers: dict[str, str],
):
	# A regular user cannot learn whether another account exists.
	other_account = await test_account_factory("other_lookup_user")

	response = await client.get(
		f"/api/accounts/{other_account['id']}", headers=user_auth_headers
	)

	assert response.status_code == 404
	assert response.json()["detail"] == "Account not found"


@pytest.mark.anyio
async def test_get_single_account_returns_not_found_for_unknown_id(
	client: AsyncClient,
	admin_auth_headers: dict[str, str],
):
	# Even an admin receives the not-found error for an absent account ID.
	response = await client.get("/api/accounts/99999", headers=admin_auth_headers)

	assert response.status_code == 404
	assert response.json()["detail"] == "Account not found"


@pytest.mark.anyio
async def test_get_single_account_rejects_missing_token(client: AsyncClient):
	# Account details cannot be requested without a bearer token.
	response = await client.get("/api/accounts/1")

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid or expired authentication token"


## Test create_account
# Verify admin creation, case-insensitive duplicate detection, and write authorization.


@pytest.mark.anyio
async def test_create_account_stores_account_for_admin(
	client: AsyncClient,
	admin_auth_headers: dict[str, str],
):
	# An admin can create an account and the response exposes only public fields.
	response = await client.post(
		"/api/accounts",
		json={"username": "new_account", "password": "longpassword"},
		headers=admin_auth_headers,
	)

	assert response.status_code == 201
	assert response.json()["username"] == "new_account"
	assert "password_hash" not in response.json()


@pytest.mark.anyio
async def test_create_account_rejects_duplicate_username(
	client: AsyncClient,
	admin_auth_headers: dict[str, str],
	test_account_factory: Callable[[str], Awaitable[dict]],
):
	# Usernames are unique without regard to letter case.
	await test_account_factory("existing_account")

	response = await client.post(
		"/api/accounts",
		json={"username": "EXISTING_ACCOUNT", "password": "longpassword"},
		headers=admin_auth_headers,
	)

	assert response.status_code == 400
	assert response.json()["detail"] == "Account with this username exists already"


@pytest.mark.anyio
async def test_create_account_rejects_missing_token(client: AsyncClient):
	# Account creation requires authentication before checking admin privileges.
	response = await client.post(
		"/api/accounts",
		json={"username": "no_token_account", "password": "longpassword"},
	)

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid or expired authentication token"


@pytest.mark.anyio
async def test_create_account_rejects_regular_user(
	client: AsyncClient,
	user_auth_headers: dict[str, str],
):
	# A logged-in regular user cannot create other accounts.
	response = await client.post(
		"/api/accounts",
		json={"username": "unauthorized_account", "password": "longpassword"},
		headers=user_auth_headers,
	)

	assert response.status_code == 403
	assert response.json()["detail"] == "Admin privileges required"


## Test login
# Exercise admin and user login, case-insensitive usernames, and generic credential failures.


@pytest.mark.anyio
async def test_login_returns_token_for_admin(client: AsyncClient):
	# The configured admin can log in and receives a bearer access token.
	response = await client.post(
		"/api/accounts/token",
		json={"username": "test_admin", "password": "test_password"},
	)

	assert response.status_code == 200
	assert response.json()["token_type"] == "bearer"
	assert response.json()["access_token"]


@pytest.mark.anyio
async def test_login_returns_token_for_existing_user(
	client: AsyncClient,
	test_account_factory: Callable[[str], Awaitable[dict]],
):
	# A user with the correct password receives a usable bearer token.
	await test_account_factory("login_user")

	response = await client.post(
		"/api/accounts/token",
		json={"username": "login_user", "password": "testpassword123"},
	)

	assert response.status_code == 200
	assert response.json()["token_type"] == "bearer"
	session_response = await client.get(
		"/api/accounts/session",
		headers={"Authorization": f"Bearer {response.json()['access_token']}"},
	)
	assert session_response.status_code == 200
	assert session_response.json() == {"valid": True}


@pytest.mark.anyio
async def test_login_is_case_insensitive_for_usernames(
	client: AsyncClient,
	test_account_factory: Callable[[str], Awaitable[dict]],
):
	# Usernames are looked up case-insensitively during login.
	await test_account_factory("CaseSensitiveUser")

	response = await client.post(
		"/api/accounts/token",
		json={"username": "casesensitiveuser", "password": "testpassword123"},
	)

	assert response.status_code == 200
	assert response.json()["token_type"] == "bearer"


@pytest.mark.anyio
async def test_login_rejects_unknown_username(client: AsyncClient):
	# An unknown username receives the generic login failure response.
	response = await client.post(
		"/api/accounts/token",
		json={"username": "unknown_user", "password": "testpassword123"},
	)

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid username or password"


@pytest.mark.anyio
async def test_login_rejects_incorrect_password(
	client: AsyncClient,
	test_account_factory: Callable[[str], Awaitable[dict]],
):
	# An incorrect password receives the same generic failure response.
	await test_account_factory("wrong_password_user")

	response = await client.post(
		"/api/accounts/token",
		json={"username": "wrong_password_user", "password": "incorrect"},
	)

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid username or password"


@pytest.mark.anyio
async def test_login_rejects_incorrect_admin_password(client: AsyncClient):
	# The configured admin account cannot log in with an incorrect password.
	response = await client.post(
		"/api/accounts/token",
		json={"username": "test_admin", "password": "incorrect"},
	)

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid username or password"
