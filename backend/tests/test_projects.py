"""Project lifecycle via the API: create, archive, restore, permanent delete.

Danger-zone guard: permanent deletion requires the caller to type the project
name, and removes the project's objects from RustFS. Archival is reversible
and keeps every object in RustFS.
"""

import pytest
from sqlalchemy import select

from src.models.file import DesignFile, FileVersion
from src.models.project import Project

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def project(db_session, test_architect, test_firm):
    proj = Project(name="Riverside Residence", owner_id=test_architect.id, firm_id=test_firm.id)
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


def _ids(projects: list[dict]) -> set[int]:
    return {p["id"] for p in projects}


async def _delete_project(
    client, url: str, headers: dict, confirmation: str | None, archive_only: bool
):
    """httpx has no json= on delete(); route it through request()."""
    import json

    return await client.request(
        "DELETE",
        url,
        params={"archive_only": archive_only},
        content=json.dumps({"confirmation": confirmation}) if confirmation is not None else None,
        headers={**headers, "Content-Type": "application/json"},
    )


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


async def test_create_project_requires_architect(client, client_auth_headers):
    """Clients cannot create projects (403)."""
    resp = await client.post(
        "/api/projects",
        json={"name": "Nope", "description": None},
        headers=client_auth_headers,
    )
    assert resp.status_code == 403, resp.text


async def test_archive_keeps_objects_and_can_be_restored(
    client, auth_headers, db_session, project, test_architect, seed_file, fake_s3
):
    """Archive hides the project but keeps its objects; restore reverts it."""
    file, _ = await seed_file(project.id, test_architect.id)
    file.thumbnail_small_key = f"thumbs/{file.id}-small.jpg"
    fake_s3.objects[file.thumbnail_small_key] = b"thumb"
    await db_session.commit()

    resp = await _delete_project(
        client,
        f"/api/projects/{project.id}",
        auth_headers,
        confirmation=project.name,
        archive_only=True,
    )
    assert resp.status_code == 204, resp.text

    # Gone from active listing, present in archived listing
    active = (await client.get("/api/projects", headers=auth_headers)).json()
    assert project.id not in _ids(active)
    archived = (
        await client.get("/api/projects", params={"archived": True}, headers=auth_headers)
    ).json()
    assert project.id in _ids(archived)
    assert next(p for p in archived if p["id"] == project.id)["is_archived"] is True

    # Objects stay in RustFS
    assert file.s3_key in fake_s3.objects
    assert file.thumbnail_small_key in fake_s3.objects

    # Restore → live again
    resp = await client.patch(
        f"/api/projects/{project.id}",
        json={"is_archived": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_archived"] is False

    active = (await client.get("/api/projects", headers=auth_headers)).json()
    assert project.id in _ids(active)


async def test_permanent_delete_requires_name_confirmation(
    client, auth_headers, project, test_architect, seed_file, fake_s3
):
    """Wrong or missing confirmation blocks deletion; project and objects survive."""
    file, _ = await seed_file(project.id, test_architect.id)

    # Wrong confirmation → 400, untouched
    resp = await _delete_project(
        client,
        f"/api/projects/{project.id}",
        auth_headers,
        confirmation="Not the project name",
        archive_only=False,
    )
    assert resp.status_code == 400, resp.text
    listing = await client.get("/api/projects", headers=auth_headers)
    assert project.id in _ids(listing.json())
    assert file.s3_key in fake_s3.objects

    # Missing confirmation body → 422 (schema validation)
    resp = await _delete_project(
        client, f"/api/projects/{project.id}", auth_headers, confirmation=None, archive_only=False
    )
    assert resp.status_code == 422, resp.text
    listing = await client.get("/api/projects", headers=auth_headers)
    assert project.id in _ids(listing.json())


async def test_permanent_delete_removes_objects_from_rustfs(
    client, auth_headers, db_session, project, test_architect, seed_file, fake_s3
):
    """Typing the name permanently deletes rows and RustFS objects."""
    file, version = await seed_file(project.id, test_architect.id)
    file.thumbnail_small_key = f"thumbs/{file.id}-small.jpg"
    file.thumbnail_medium_key = f"thumbs/{file.id}-medium.jpg"
    fake_s3.objects[file.thumbnail_small_key] = b"t1"
    fake_s3.objects[file.thumbnail_medium_key] = b"t2"
    await db_session.commit()

    resp = await _delete_project(
        client,
        f"/api/projects/{project.id}",
        auth_headers,
        confirmation=project.name,
        archive_only=False,
    )
    assert resp.status_code == 204, resp.text

    # Gone from both listings
    active = (await client.get("/api/projects", headers=auth_headers)).json()
    archived = (
        await client.get("/api/projects", params={"archived": True}, headers=auth_headers)
    ).json()
    assert project.id not in _ids(active)
    assert project.id not in _ids(archived)

    # DB rows removed
    assert (
        await db_session.execute(select(Project).where(Project.id == project.id))
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(select(DesignFile).where(DesignFile.project_id == project.id))
    ).scalars().all() == []
    assert (
        await db_session.execute(select(FileVersion).where(FileVersion.file_id == file.id))
    ).scalars().all() == []

    # RustFS objects removed
    assert file.s3_key not in fake_s3.objects
    assert file.thumbnail_small_key not in fake_s3.objects
    assert file.thumbnail_medium_key not in fake_s3.objects
    assert set(fake_s3.deleted) >= {
        file.s3_key,
        file.thumbnail_small_key,
        file.thumbnail_medium_key,
    }
    assert version.s3_key in fake_s3.deleted
