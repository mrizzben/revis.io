"""Google OAuth flow: authorize redirect, callback login/signup, state validation.

Google's token/userinfo endpoints are monkeypatched; the flow tested here is the
redirect chain + find-or-create user logic that runs server-side.
"""

import pytest
from sqlalchemy import select

from src.core.config import settings
from src.core.security import decode_token
from src.models.user import User
from src.services import oauth as oauth_service


@pytest.fixture
async def oauth_client(db_session):
    """Client over https: the app's secure cookies must round-trip.

    Real browsers send Secure cookies to localhost; httpx strictly enforces the
    Secure flag, so OAuth tests run over an https base URL.
    """
    from httpx import ASGITransport, AsyncClient

    from src.core.database import get_db
    from src.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _clear_oauth_rate_limit():
    """Reset the module-level callback rate limiter between tests (same fake IP)."""
    from src.api.routes import auth as auth_routes

    auth_routes.oauth_callback_limiter.requests.clear()
    yield
    auth_routes.oauth_callback_limiter.requests.clear()


@pytest.fixture(autouse=True)
def _enable_google_oauth(monkeypatch):
    """Turn OAuth on (config default is disabled) and stub Google's HTTP endpoints."""
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-client-secret")

    async def _fake_exchange(code: str) -> dict:
        assert code == "valid-code", "token exchange must receive the authorization code"
        return {"access_token": "fake-google-access-token", "token_type": "Bearer"}

    async def _fake_userinfo(access_token: str) -> dict:
        assert access_token == "fake-google-access-token"
        return {
            "sub": "google-123",
            "email": "oauth.user@example.com",
            "email_verified": True,
            "name": "OAuth User",
            "picture": "https://example.com/pic.png",
        }

    monkeypatch.setattr(oauth_service, "exchange_code_for_tokens", _fake_exchange)
    monkeypatch.setattr(oauth_service, "fetch_google_userinfo", _fake_userinfo)


async def _start_oauth(client) -> str:
    """Start the flow and return the state value from the oauth_state cookie."""
    resp = await client.get("/api/auth/google/authorize", follow_redirects=False)
    assert resp.status_code == 302, resp.text
    state = client.cookies.get("oauth_state")
    assert state, "state cookie must be set"
    return state


@pytest.mark.asyncio
async def test_authorize_redirects_to_google_with_state(oauth_client):
    """Authorize builds a Google consent URL and stores a CSRF state cookie."""
    resp = await oauth_client.get("/api/auth/google/authorize", follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=test-client-id" in location
    assert "redirect_uri=" in location
    assert "state=" in location
    assert "response_type=code" in location
    assert oauth_client.cookies.get("oauth_state")


@pytest.mark.asyncio
async def test_authorize_disabled_returns_503(oauth_client, monkeypatch):
    """With no Google client id configured, authorize returns 503."""
    monkeypatch.setattr(oauth_service, "oauth_enabled", lambda: False)
    resp = await oauth_client.get("/api/auth/google/authorize", follow_redirects=False)
    assert resp.status_code == 503, resp.text


@pytest.mark.asyncio
async def test_providers_reflects_oauth_config(oauth_client, monkeypatch):
    """Providers endpoint reports google availability from config."""
    resp = await oauth_client.get("/api/auth/providers")
    assert resp.status_code == 200
    assert resp.json() == {"google": True}

    monkeypatch.setattr(oauth_service, "oauth_enabled", lambda: False)
    resp = await oauth_client.get("/api/auth/providers")
    assert resp.json() == {"google": False}


@pytest.mark.asyncio
async def test_callback_creates_new_user(oauth_client, db_session):
    """First-time Google login creates an architect user and redirects with tokens."""
    state = await _start_oauth(oauth_client)

    resp = await oauth_client.get(
        f"/api/auth/google/callback?code=valid-code&state={state}",
        follow_redirects=False,
    )
    assert resp.status_code == 302, resp.text
    location = resp.headers["location"]
    assert location.startswith("http://localhost:5173/oauth/callback#access_token=")
    assert "token_type=bearer" in location

    # Refresh token cookie is set (same contract as password login)
    set_cookie = resp.headers.get("set-cookie", "")
    assert "refresh_token=" in set_cookie
    assert "HttpOnly" in set_cookie

    result = await db_session.execute(select(User).where(User.email == "oauth.user@example.com"))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.name == "OAuth User"
    assert user.role.value == "architect"
    assert user.is_verified is True
    assert user.hashed_password is None  # OAuth-only: no password


@pytest.mark.asyncio
async def test_callback_links_existing_email(oauth_client, db_session, test_architect, monkeypatch):
    """Google login with an already-registered email logs into that account."""

    async def _existing_userinfo(access_token: str) -> dict:
        return {"email": test_architect.email, "name": "Test Architect"}

    monkeypatch.setattr(oauth_service, "fetch_google_userinfo", _existing_userinfo)

    state = await _start_oauth(oauth_client)
    resp = await oauth_client.get(
        f"/api/auth/google/callback?code=valid-code&state={state}",
        follow_redirects=False,
    )
    assert resp.status_code == 302, resp.text

    result = await db_session.execute(select(User).where(User.email == test_architect.email))
    users = result.scalars().all()
    assert len(users) == 1, "no duplicate user row may be created"
    assert users[0].id == test_architect.id

    # The access token issued belongs to the linked user
    token = resp.headers["location"].split("access_token=")[1].split("&")[0]
    assert decode_token(token)["sub"] == str(test_architect.id)


@pytest.mark.asyncio
async def test_callback_state_mismatch_rejected(oauth_client):
    """Callback with a wrong/missing state is rejected with an error redirect."""
    resp = await oauth_client.get(
        "/api/auth/google/callback?code=valid-code&state=attacker-state",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "error=invalid_state" in resp.headers["location"]


@pytest.mark.asyncio
async def test_oauth_user_cannot_password_login(oauth_client, db_session):
    """An OAuth-only user (no password) gets 401, not 500, on password login."""
    user = User(
        email="oauth.only@example.com",
        name="OAuth Only",
        hashed_password=None,
        role="architect",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await oauth_client.post(
        "/api/auth/login",
        data={"username": "oauth.only@example.com", "password": "whatever123"},
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_callback_no_code_redirects_to_login(oauth_client):
    """Callback without a code (and no error) falls back to the login page."""
    state = await _start_oauth(oauth_client)
    resp = await oauth_client.get(
        f"/api/auth/google/callback?state={state}",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"].endswith("/login?error=google_oauth_failed")
