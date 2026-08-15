"""End-to-end auth flow: registration, login, token-protected user lookup.

Regression guard for the docker-compose registration failure: with a migrated
database, a fresh user must be able to register and immediately log in.
"""

import pytest

from src.models.user import User


@pytest.fixture(autouse=True)
def _clear_register_rate_limit():
    """Reset the module-level register rate limiter between tests.

    httpx.ASGITransport stamps every request with the same fake client IP, so the
    register limiter (3 req / hr, tracked in-memory) would otherwise trip a 429
    once a test file performs more than three registrations.
    """
    from src.api.routes import auth as auth_routes

    auth_routes.register_limiter.requests.clear()
    yield
    auth_routes.register_limiter.requests.clear()


@pytest.mark.asyncio
async def test_register_login_me_flow(client):
    """Architect registers, logs in, and fetches their own profile."""
    # Register
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "newarch@test.com",
            "password": "password123",
            "name": "New Architect",
            "role": "architect",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"] > 0

    # Login with the same credentials (form-encoded, as the SPA does)
    resp = await client.post(
        "/api/auth/login",
        data={"username": "newarch@test.com", "password": "password123"},
    )
    assert resp.status_code == 200, resp.text
    tokens = resp.json()
    assert tokens["access_token"]

    # Use the token to fetch the profile
    resp = await client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "newarch@test.com"


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(client, test_architect):
    """Registering an existing email returns a 400 with a readable detail."""
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": test_architect.email,
            "password": "password123",
            "name": "Duplicate",
            "role": "architect",
        },
    )
    assert resp.status_code == 400, resp.text
    assert isinstance(resp.json()["detail"], str)
    assert "already exists" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_register_client_requires_invitation_token(client):
    """Client role without an invitation token is rejected with a readable detail."""
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "newclient@test.com",
            "password": "password123",
            "name": "New Client",
            "role": "client",
        },
    )
    assert resp.status_code == 400, resp.text
    assert isinstance(resp.json()["detail"], str)
    assert "invitation" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_register_login_creates_user_row(client, db_session):
    """Registration persists the user so login can find them."""
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "persist@test.com",
            "password": "password123",
            "name": "Persist Me",
            "role": "architect",
        },
    )
    assert resp.status_code == 201, resp.text
    from sqlalchemy import select

    result = await db_session.execute(select(User).where(User.email == "persist@test.com"))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.name == "Persist Me"
    assert user.role.value == "architect"
