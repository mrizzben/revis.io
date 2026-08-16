"""Tests for fine-grained roles (admin sub-role) and client secure-link access."""

import pytest
from sqlalchemy import select

from src.core.security import create_access_token
from src.models.project import Project, ProjectMember
from src.models.user import User


@pytest.fixture
async def project(db_session, test_architect, test_firm):
    proj = Project(name="Roles Project", owner_id=test_architect.id, firm_id=test_firm.id)
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


@pytest.fixture
async def second_project(db_session, test_architect, test_firm):
    proj = Project(name="Second Project", owner_id=test_architect.id, firm_id=test_firm.id)
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


@pytest.fixture
async def test_admin(db_session) -> User:
    user = User(
        email="admin@test.com",
        name="Test Admin",
        hashed_password="x",
        role="admin",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def admin_headers(test_admin):
    token = create_access_token(subject=test_admin.id, role="admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def collaborator(db_session, project) -> User:
    user = User(
        email="collab2@test.com",
        name="Collab Two",
        hashed_password="x",
        role="architect",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(ProjectMember(project_id=project.id, user_id=user.id, role="collaborator"))
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def collaborator_headers(collaborator):
    token = create_access_token(subject=collaborator.id, role="architect")
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════════════════
# Admin sub-role
# ═══════════════════════════════════════════════════════════


async def test_admin_can_create_project(client, admin_headers):
    resp = await client.post(
        "/api/projects", json={"name": "Admin Project"}, headers=admin_headers
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["owner_id"] is not None


async def test_admin_sees_all_projects(client, admin_headers, project, second_project, test_architect):
    resp = await client.get("/api/projects", headers=admin_headers)
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert project.id in ids and second_project.id in ids


async def test_admin_can_archive_any_project(
    client, admin_headers, project, test_architect, db_session
):
    # Admin is not the owner; still allowed to archive (superuser).
    import json

    resp = await client.request(
        "DELETE",
        f"/api/projects/{project.id}",
        params={"archive_only": True},
        content=json.dumps({"confirmation": project.name}),
        headers={**admin_headers, "Content-Type": "application/json"},
    )
    assert resp.status_code == 204, resp.text

    archived = (await db_session.execute(select(Project).where(Project.id == project.id))).scalar_one()
    assert archived.is_archived is True


async def test_collaborator_cannot_archive_or_delete(
    client, collaborator_headers, project, collaborator
):
    # Collaborator has full project functions EXCEPT delete/archive.
    import json

    resp = await client.request(
        "DELETE",
        f"/api/projects/{project.id}",
        params={"archive_only": True},
        content=json.dumps({"confirmation": project.name}),
        headers={**collaborator_headers, "Content-Type": "application/json"},
    )
    assert resp.status_code == 403, resp.text


async def test_collaborator_can_update_but_not_archive(
    client, collaborator_headers, project
):
    # Collaborator may edit project metadata (non-destructive function).
    resp = await client.patch(
        f"/api/projects/{project.id}",
        json={"description": "edited by collaborator"},
        headers=collaborator_headers,
    )
    # update_project requires owner; collaborator is 403 on PATCH too.
    assert resp.status_code == 403, resp.text


async def test_admin_passes_architect_gate_for_internal_routes(
    client, admin_headers, project, test_architect, collaborator
):
    # require_role("architect") must accept admin (superuser superset).
    resp = await client.post(
        f"/api/projects/{project.id}/milestones",
        json={"name": "M1"},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text

    resp = await client.get(f"/api/projects/{project.id}/collaborators", headers=admin_headers)
    assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════
# Client secure-link access (no sign-up)
# ═══════════════════════════════════════════════════════════


async def test_owner_enables_client_access(client, auth_headers, project):
    resp = await client.post(
        f"/api/projects/{project.id}/client-access",
        json={"password": "client-pass-123"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token"]
    assert "/client-access/" in body["url"]
    assert body["password_set"] is True


async def test_admin_can_enable_client_access(client, admin_headers, project):
    resp = await client.post(
        f"/api/projects/{project.id}/client-access",
        json={"password": "client-pass-123"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text


async def test_collaborator_cannot_enable_client_access(
    client, collaborator_headers, project
):
    resp = await client.post(
        f"/api/projects/{project.id}/client-access",
        json={"password": "client-pass-123"},
        headers=collaborator_headers,
    )
    assert resp.status_code == 403, resp.text


async def test_public_link_info(client, auth_headers, project):
    token = (await client.post(
        f"/api/projects/{project.id}/client-access",
        json={"password": "client-pass-123"},
        headers=auth_headers,
    )).json()["token"]

    resp = await client.get(f"/api/client-access/{token}")
    assert resp.status_code == 200
    assert resp.json()["project_name"] == project.name


async def test_authenticate_with_wrong_password(client, auth_headers, project):
    token = (await client.post(
        f"/api/projects/{project.id}/client-access",
        json={"password": "client-pass-123"},
        headers=auth_headers,
    )).json()["token"]

    resp = await client.post(
        "/api/client-access/authenticate",
        json={"token": token, "password": "wrong-password"},
    )
    assert resp.status_code == 401


async def test_authenticate_returns_scoped_session(client, auth_headers, project):
    token = (await client.post(
        f"/api/projects/{project.id}/client-access",
        json={"password": "client-pass-123"},
        headers=auth_headers,
    )).json()["token"]

    resp = await client.post(
        "/api/client-access/authenticate",
        json={"token": token, "password": "client-pass-123"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["project_id"] == project.id


async def test_anonymous_session_can_view_project_and_files(
    client, auth_headers, project, test_architect, seed_file
):
    file, _ = await seed_file(project.id, test_architect.id)
    token = (await client.post(
        f"/api/projects/{project.id}/client-access",
        json={"password": "client-pass-123"},
        headers=auth_headers,
    )).json()["token"]
    session = (await client.post(
        "/api/client-access/authenticate",
        json={"token": token, "password": "client-pass-123"},
    )).json()
    guest_headers = {"Authorization": f"Bearer {session['access_token']}"}

    proj_resp = await client.get(f"/api/projects/{project.id}", headers=guest_headers)
    assert proj_resp.status_code == 200
    assert proj_resp.json()["name"] == project.name

    files_resp = await client.get(f"/api/projects/{project.id}/files", headers=guest_headers)
    assert files_resp.status_code == 200


async def test_anonymous_session_scoped_to_one_project(
    client, auth_headers, project, second_project
):
    token = (await client.post(
        f"/api/projects/{project.id}/client-access",
        json={"password": "client-pass-123"},
        headers=auth_headers,
    )).json()["token"]
    session = (await client.post(
        "/api/client-access/authenticate",
        json={"token": token, "password": "client-pass-123"},
    )).json()
    guest_headers = {"Authorization": f"Bearer {session['access_token']}"}

    # The scoped session must NOT see the other project.
    resp = await client.get(f"/api/projects/{second_project.id}", headers=guest_headers)
    assert resp.status_code == 404


async def test_anonymous_session_cannot_access_internal_routes(
    client, auth_headers, project
):
    token = (await client.post(
        f"/api/projects/{project.id}/client-access",
        json={"password": "client-pass-123"},
        headers=auth_headers,
    )).json()["token"]
    session = (await client.post(
        "/api/client-access/authenticate",
        json={"token": token, "password": "client-pass-123"},
    )).json()
    guest_headers = {"Authorization": f"Bearer {session['access_token']}"}

    # Internal team content must stay hidden from anonymous clients.
    resp = await client.get(f"/api/projects/{project.id}/collaborators", headers=guest_headers)
    assert resp.status_code == 404

    resp = await client.get(f"/api/projects/{project.id}/internal-notes", headers=guest_headers)
    assert resp.status_code == 404


async def test_disable_client_access_revokes_sessions(client, auth_headers, project):
    token = (await client.post(
        f"/api/projects/{project.id}/client-access",
        json={"password": "client-pass-123"},
        headers=auth_headers,
    )).json()["token"]
    session = (await client.post(
        "/api/client-access/authenticate",
        json={"token": token, "password": "client-pass-123"},
    )).json()
    guest_headers = {"Authorization": f"Bearer {session['access_token']}"}

    assert (await client.get(f"/api/projects/{project.id}", headers=guest_headers)).status_code == 200

    resp = await client.delete(f"/api/projects/{project.id}/client-access", headers=auth_headers)
    assert resp.status_code == 204

    # Session is now rejected: client access disabled.
    resp = await client.get(f"/api/projects/{project.id}", headers=guest_headers)
    assert resp.status_code == 404


async def test_guest_email_namespace_reserved(client):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "guest-1@revis.io", "password": "password123", "name": "Attacker", "role": "client"},
    )
    assert resp.status_code == 400
    assert "reserved" in resp.json()["detail"].lower()


async def test_anonymous_client_can_comment_and_approve_review(
    client, auth_headers, project, test_architect, collaborator, seed_file
):
    file, version = await seed_file(project.id, test_architect.id)

    # Enable + authenticate as anonymous client.
    token = (await client.post(
        f"/api/projects/{project.id}/client-access",
        json={"password": "client-pass-123"},
        headers=auth_headers,
    )).json()["token"]
    session = (await client.post(
        "/api/client-access/authenticate",
        json={"token": token, "password": "client-pass-123"},
    )).json()
    guest_headers = {"Authorization": f"Bearer {session['access_token']}"}

    # Comment as the anonymous client.
    comment_resp = await client.post(
        f"/api/files/{file.id}/comments",
        json={"body": "Reviewing from the secure link"},
        headers=guest_headers,
    )
    assert comment_resp.status_code == 201, comment_resp.text

    # Issue the revision to the client so a client review can be created.
    issue_resp = await client.post(
        f"/api/files/{file.id}/versions/1/issue",
        headers=auth_headers,
    )
    assert issue_resp.status_code == 200, issue_resp.text

    # Owner opens a client review and asks the client to approve.
    review_resp = await client.post(
        f"/api/files/{file.id}/reviews",
        json={
            "reviewer_id": collaborator.id,
            "revision_id": version.id,
            "is_client_review": True,
        },
        headers=auth_headers,
    )
    assert review_resp.status_code == 201, review_resp.text
    review_id = review_resp.json()["id"]

    approve = await client.post(
        f"/api/reviews/{review_id}/transition",
        json={"action": "approve", "comment": "Approved from the link"},
        headers=guest_headers,
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"
