import asyncio
import os
import sys
from collections.abc import AsyncGenerator, Awaitable, Callable

# Use the selector event loop required by the async SQLite driver on Windows.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Set test configuration before importing the app, which reads these values at import time.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_tool.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"

os.environ["ADMIN"] = "test_admin"
os.environ["ADMIN_PASSWORD"] = "test_password"


import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from database import Base, get_db
from main import app

# Enable AnyIO's pytest integration so async tests and fixtures can run.
pytest_plugins = ["anyio"]


# Keep async tests on asyncio, matching the async database driver used here.
@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


## Test Engine
# Share one engine for the test session while opening isolated connections as needed.
@pytest.fixture(scope="session")
def test_engine():
    engine = create_async_engine(
        os.environ["DATABASE_URL"],
        poolclass=NullPool,
    )
    return engine


## Setup Database
# Create the schema once, then remove it and dispose of the engine after the suite.
@pytest.fixture(scope="session")
async def setup_database(test_engine):
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


## DB Session (Transactional Rollback)
# Give each test a database session and clear rows left by committed savepoints.
@pytest.fixture
async def db_session(
    test_engine,
    setup_database,
) -> AsyncGenerator[AsyncSession]:
    # Clear committed data left by earlier tests before opening this test's transaction.
    async with test_engine.begin() as cleanup_connection:
        for table in reversed(Base.metadata.sorted_tables):
            await cleanup_connection.execute(table.delete())

    conn = await test_engine.connect()
    trans = await conn.begin()

    test_async_session = async_sessionmaker(
        bind=conn,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    async with test_async_session() as session:
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
            await conn.close()


## Client Fixture: swaps out functions for test functions
# Route HTTP requests through the FastAPI app without starting a network server.
# Override get_db so requests use the test's session, then remove the override afterward.
@pytest.fixture
async def client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient]:

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


## Auth Helpers


### log in the admin
# Log in with the configured test admin and return a ready-to-use bearer header.
async def login_test_admin(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/accounts/token",
        json={
            "username": os.environ["ADMIN"],
            "password": os.environ["ADMIN_PASSWORD"],
        },
    )
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# Provide admin bearer headers directly to tests that exercise admin-only routes.
@pytest.fixture
async def admin_auth_headers(client: AsyncClient) -> dict[str, str]:
    return await login_test_admin(client)


### create a test account
# Create a regular account through the protected endpoint and return its public data.
async def create_test_account(
    client: AsyncClient,
    username: str = "testaccount",
    password: str = "testpassword123",
) -> dict:
    admin_headers = await login_test_admin(client)
    response = await client.post(
        "/api/accounts",
        json={
            "username": username,
            "password": password,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, f"Failed to create user: {response.text}"
    return response.json()


# Let a test create multiple accounts while keeping the client setup in one fixture.
@pytest.fixture
async def test_account_factory(
    client: AsyncClient,
) -> Callable[[str], Awaitable[dict]]:
    async def create_account(username: str) -> dict:
        return await create_test_account(client, username=username)

    return create_account


# Create a regular account, log in, and return its bearer header for authorization tests.
async def create_test_user_auth_headers(
    client: AsyncClient,
    username: str,
    password: str = "testpassword123",
) -> dict[str, str]:
    await create_test_account(client, username=username, password=password)
    response = await client.post(
        "/api/accounts/token",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, f"User login failed: {response.text}"
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# Supply a standard logged-in user to tests that need only one regular account.
@pytest.fixture
async def user_auth_headers(client: AsyncClient) -> dict[str, str]:
    return await create_test_user_auth_headers(client, "test_user")
