from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient

from config import settings


def expired_access_token() -> str:
    return jwt.encode(
        {
            "sub": settings.admin,
            "role": "admin",
            "exp": datetime.now(UTC) - timedelta(seconds=1),
        },
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )


@pytest.mark.anyio
async def test_expired_page_session_redirects_to_expired_session_screen(
    client: AsyncClient,
):
    response = await client.get(
        "/chapters/1/exercises/1",
        headers={
            "Accept": "text/html",
            "Cookie": f"access_token={expired_access_token()}",
        },
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith("/session-expired")


@pytest.mark.anyio
async def test_missing_page_session_redirects_to_login(client: AsyncClient):
    response = await client.get(
        "/chapters/1/exercises/1",
        headers={"Accept": "text/html"},
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith("/login")


@pytest.mark.anyio
async def test_expired_home_session_redirects_to_expired_session_screen(
    client: AsyncClient,
):
    response = await client.get(
        "/",
        headers={
            "Accept": "text/html",
            "Cookie": f"access_token={expired_access_token()}",
        },
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith("/session-expired")


@pytest.mark.anyio
async def test_session_expired_page_uses_shared_layout_and_links_to_login(
    client: AsyncClient,
):
    response = await client.get("/session-expired")

    assert response.status_code == 200
    assert 'class="site-header"' in response.text
    assert "Deine Anmeldung ist abgelaufen." in response.text
    assert 'href="http://test/login"' in response.text
    assert "Max-Age=0" in response.headers["set-cookie"]


@pytest.mark.anyio
async def test_api_unauthorized_responses_remain_json(
    client: AsyncClient,
):
    response = await client.get(
        "/api/accounts/session",
        headers={
            "Accept": "text/html",
            "Cookie": f"access_token={expired_access_token()}",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired authentication token"


@pytest.mark.anyio
async def test_browser_not_found_uses_error_page(client: AsyncClient):
    response = await client.get(
        "/page-that-does-not-exist",
        headers={"Accept": "text/html"},
    )

    assert response.status_code == 404
    assert "Die angeforderte Seite wurde nicht gefunden." in response.text
