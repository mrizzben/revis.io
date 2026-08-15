"""Project creation via the API.

Regression guard: creating a project used to return 500 because the service
passed the reserved LogRecord key `name` to logging `extra` (Python raises
KeyError "Attempt to overwrite 'name' in LogRecord"). The frontend then saw
failure, kept the modal open, and never refreshed the list.
"""

import pytest


@pytest.mark.asyncio
async def test_create_project_via_api(client, auth_headers):
    """Architect creates a project; response is 201 and it appears in the list."""
    resp = await client.post(
        "/api/projects",
        json={"name": "Riverside Residence", "description": "A riverside house"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Riverside Residence"
    assert body["id"] > 0

    listing = await client.get("/api/projects", headers=auth_headers)
    assert listing.status_code == 200, listing.text
    names = [p["name"] for p in listing.json()]
    assert "Riverside Residence" in names


@pytest.mark.asyncio
async def test_create_project_requires_architect(client, client_auth_headers):
    """Clients cannot create projects (403)."""
    resp = await client.post(
        "/api/projects",
        json={"name": "Nope", "description": None},
        headers=client_auth_headers,
    )
    assert resp.status_code == 403, resp.text
