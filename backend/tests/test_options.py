"""Tests for T5 — design options."""

import uuid

import pytest

from src.models.project import Project


@pytest.fixture
async def project(db_session, test_architect, test_firm):
    proj = Project(name="Options Project", owner_id=test_architect.id, firm_id=test_firm.id)
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


async def test_create_and_list_options(client, auth_headers, project, test_architect):
    resp = await client.post(
        f"/api/projects/{project.id}/options",
        json={"name": "Option A", "description": "Courtyard scheme"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Option A"

    resp = await client.post(
        f"/api/projects/{project.id}/options",
        json={"name": "Option B"},
        headers=auth_headers,
    )
    assert resp.status_code == 201

    options = (await client.get(f"/api/projects/{project.id}/options", headers=auth_headers)).json()
    assert {o["name"] for o in options} == {"Option A", "Option B"}


async def test_promote_option_as_current(
    client, auth_headers, project, test_architect
):
    a = (await client.post(
        f"/api/projects/{project.id}/options", json={"name": "Option A"}, headers=auth_headers
    )).json()
    b = (await client.post(
        f"/api/projects/{project.id}/options", json={"name": "Option B"}, headers=auth_headers
    )).json()

    # Promote B → only B is current.
    resp = await client.patch(
        f"/api/options/{b['id']}", json={"is_current": True}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["is_current"] is True

    options = (await client.get(f"/api/projects/{project.id}/options", headers=auth_headers)).json()
    current = [o for o in options if o["is_current"]]
    assert len(current) == 1
    assert current[0]["id"] == b["id"]

    # Promote A → B loses current.
    await client.patch(f"/api/options/{a['id']}", json={"is_current": True}, headers=auth_headers)
    options = (await client.get(f"/api/projects/{project.id}/options", headers=auth_headers)).json()
    current = [o for o in options if o["is_current"]]
    assert len(current) == 1 and current[0]["id"] == a["id"]


async def test_fork_copies_revision_history(
    client, auth_headers, project, test_architect, seed_file, fake_s3
):
    option = (await client.post(
        f"/api/projects/{project.id}/options", json={"name": "Courtyard scheme"}, headers=auth_headers
    )).json()
    file, v1 = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    key = f"uploads/{uuid.uuid4()}/v2.pdf"
    fake_s3.objects[key] = b"%PDF-1.4 v2"
    await client.post(
        f"/api/files/{file.id}/upload-complete", params={"key": key}, headers=auth_headers
    )

    resp = await client.post(
        f"/api/options/{option['id']}/fork", json={"file_id": str(file.id)}, headers=auth_headers
    )
    assert resp.status_code == 201, resp.text
    fork = resp.json()
    assert fork["id"] != str(file.id)
    assert fork["design_option_id"] == option["id"]
    assert fork["parent_file_id"] == str(file.id)
    assert fork["version_count"] == 2

    # Option file list includes the fork with its own version history.
    files = (await client.get(f"/api/options/{option['id']}/files", headers=auth_headers)).json()
    assert len(files) == 1
    assert [v["version_number"] for v in files[0]["versions"]] == [1, 2]


async def test_archive_option_hides_from_client_view(
    client, auth_headers, client_auth_headers, project, test_architect, seed_file, fake_s3, db_session
):
    from src.models.project import ProjectMember as PM

    option = (await client.post(
        f"/api/projects/{project.id}/options", json={"name": "Rejected scheme"}, headers=auth_headers
    )).json()
    file, v1 = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    await client.post(f"/api/files/{file.id}/versions/1/issue", headers=auth_headers)
    # Move the file into the option.
    await client.post(f"/api/options/{option['id']}/fork", json={"file_id": str(file.id)}, headers=auth_headers)

    client_user = (await db_session.execute(
        __import__("sqlalchemy").select(__import__("src.models.user", fromlist=["User"]).User).where(
            __import__("src.models.user", fromlist=["User"]).User.email == "client@test.com"
        )
    )).scalar_one()
    db_session.add(PM(project_id=project.id, user_id=client_user.id, role="client"))
    await db_session.commit()

    # Client sees the option before archiving.
    options = (await client.get(f"/api/projects/{project.id}/options", headers=client_auth_headers)).json()
    assert any(o["id"] == option["id"] for o in options)

    # Archive it → gone from client view, still listed internally.
    await client.patch(f"/api/options/{option['id']}", json={"is_archived": True}, headers=auth_headers)
    options = (await client.get(f"/api/projects/{project.id}/options", headers=client_auth_headers)).json()
    assert not any(o["id"] == option["id"] for o in options)

    options_internal = (await client.get(f"/api/projects/{project.id}/options", headers=auth_headers)).json()
    assert any(o["id"] == option["id"] for o in options_internal)


async def test_client_cannot_manage_options(
    client, client_auth_headers, project, test_architect, seed_file, db_session
):
    from src.models.project import ProjectMember as PM

    client_user = (await db_session.execute(
        __import__("sqlalchemy").select(__import__("src.models.user", fromlist=["User"]).User).where(
            __import__("src.models.user", fromlist=["User"]).User.email == "client@test.com"
        )
    )).scalar_one()
    db_session.add(PM(project_id=project.id, user_id=client_user.id, role="client"))
    await db_session.commit()

    resp = await client.post(
        f"/api/projects/{project.id}/options", json={"name": "Nope"}, headers=client_auth_headers
    )
    assert resp.status_code == 403
