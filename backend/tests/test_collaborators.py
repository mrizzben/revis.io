"""Tests for collaborator routes: add/remove/list and role-based access."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.models.project import Project, ProjectMember
from src.models.user import User


@pytest.fixture
async def project(db_session, test_architect, test_firm):
    proj = Project(name="Collab Project", owner_id=test_architect.id, firm_id=test_firm.id)
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


@pytest.fixture
async def teammate(db_session, test_firm) -> User:
    user = User(
        email="teammate@test.com",
        name="Teammate",
        hashed_password="x",
        role="architect",
        is_verified=True,
        firm_id=test_firm.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def teammate_headers(db_session, teammate):
    from src.core.security import create_access_token

    token = create_access_token(subject=teammate.id, role="architect", firm_id=teammate.firm_id)
    return {"Authorization": f"Bearer {token}"}


async def test_owner_adds_collaborator(client: AsyncClient, auth_headers, project, teammate):
    resp = await client.post(
        f"/api/projects/{project.id}/collaborators",
        json={"user_id": teammate.id},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user_id"] == teammate.id
    assert body["role"] == "collaborator"

    result = await client.get(f"/api/projects/{project.id}/collaborators", headers=auth_headers)
    assert result.status_code == 200
    members = result.json()
    assert members["owner"]["user_id"] == project.owner_id
    assert any(c["user_id"] == teammate.id for c in members["collaborators"])


async def test_add_collaborator_by_email_is_idempotent(
    client: AsyncClient, auth_headers, project, teammate
):
    for _ in range(2):
        resp = await client.post(
            f"/api/projects/{project.id}/collaborators",
            json={"email": teammate.email},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "collaborator"


async def test_non_owner_collaborator_cannot_add_members(
    client: AsyncClient, auth_headers, teammate_headers, project, teammate, db_session
):
    # Promote teammate to collaborator first
    db_session.add(ProjectMember(project_id=project.id, user_id=teammate.id, role="collaborator"))
    await db_session.commit()

    another = User(
        email="another@test.com",
        name="Another",
        hashed_password="x",
        role="architect",
        is_verified=True,
    )
    db_session.add(another)
    await db_session.commit()
    await db_session.refresh(another)

    resp = await client.post(
        f"/api/projects/{project.id}/collaborators",
        json={"user_id": another.id},
        headers=teammate_headers,
    )
    assert resp.status_code == 403


async def test_client_cannot_access_collaborator_endpoints(
    client: AsyncClient, client_auth_headers, project
):
    resp = await client.get(
        f"/api/projects/{project.id}/collaborators", headers=client_auth_headers
    )
    assert resp.status_code == 404


async def test_owner_removes_collaborator_revokes_access(
    client: AsyncClient, auth_headers, teammate_headers, project, teammate, db_session
):
    db_session.add(ProjectMember(project_id=project.id, user_id=teammate.id, role="collaborator"))
    await db_session.commit()

    resp = await client.delete(
        f"/api/projects/{project.id}/collaborators/{teammate.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 204

    # Teammate no longer has internal access: 404
    resp2 = await client.get(f"/api/projects/{project.id}/collaborators", headers=teammate_headers)
    assert resp2.status_code == 404

    result = await db_session.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == teammate.id,
        )
    )
    assert result.scalar_one_or_none() is None


async def test_cannot_add_owner_as_collaborator(
    client: AsyncClient, auth_headers, project, test_architect
):
    resp = await client.post(
        f"/api/projects/{project.id}/collaborators",
        json={"user_id": test_architect.id},
        headers=auth_headers,
    )
    assert resp.status_code == 400


async def test_cannot_remove_owner(client: AsyncClient, auth_headers, project, test_architect):
    resp = await client.delete(
        f"/api/projects/{project.id}/collaborators/{test_architect.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 400


async def test_removing_collaborator_reassigns_open_todos_to_owner(
    client: AsyncClient, auth_headers, project, teammate, db_session
):
    from src.models.todo import ToDo

    db_session.add(ProjectMember(project_id=project.id, user_id=teammate.id, role="collaborator"))
    db_session.add(
        ToDo(
            project_id=project.id,
            created_by=project.owner_id,
            title="Open todo",
            assignee_id=teammate.id,
            status="open",
        )
    )
    db_session.add(
        ToDo(
            project_id=project.id,
            created_by=project.owner_id,
            title="Done todo",
            assignee_id=teammate.id,
            status="complete",
        )
    )
    await db_session.commit()

    resp = await client.delete(
        f"/api/projects/{project.id}/collaborators/{teammate.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 204

    result = await db_session.execute(select(ToDo).where(ToDo.project_id == project.id))
    todos = result.scalars().all()
    by_title = {t.title: t for t in todos}
    # Open todo reassigned to owner; completed todo left untouched
    assert by_title["Open todo"].assignee_id == project.owner_id
    assert by_title["Done todo"].assignee_id == teammate.id
