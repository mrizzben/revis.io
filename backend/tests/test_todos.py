"""Tests for to-dos: create, assign, status updates, notifications, visibility."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.models.notification import Notification, NotificationType
from src.models.project import Project, ProjectMember


@pytest.fixture
async def project(db_session, test_architect, test_firm):
    proj = Project(name="Todos Project", owner_id=test_architect.id, firm_id=test_firm.id)
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


@pytest.fixture
async def collaborator(db_session, test_firm):
    from src.models.user import User

    user = User(
        email="todo-collab@test.com",
        name="Todo Collab",
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
async def collab_headers(db_session, collaborator):
    from src.core.security import create_access_token

    token = create_access_token(
        subject=collaborator.id, role="architect", firm_id=collaborator.firm_id
    )
    return {"Authorization": f"Bearer {token}"}


async def test_owner_creates_and_assigns_todo(
    client: AsyncClient, auth_headers, project, collaborator, db_session
):
    db_session.add(
        ProjectMember(project_id=project.id, user_id=collaborator.id, role="collaborator")
    )
    await db_session.commit()

    resp = await client.post(
        f"/api/projects/{project.id}/todos",
        json={"title": "Ship milestone notes", "assignee_id": collaborator.id},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "open"
    assert body["assignee"]["id"] == collaborator.id

    # Assignee got a notification
    notif_result = await db_session.execute(
        select(Notification).where(
            Notification.user_id == collaborator.id,
            Notification.type == NotificationType.todo_assigned,
        )
    )
    assert notif_result.scalar_one_or_none() is not None


async def test_assignee_completes_todo(
    client: AsyncClient, auth_headers, project, collaborator, collab_headers, db_session
):
    db_session.add(
        ProjectMember(project_id=project.id, user_id=collaborator.id, role="collaborator")
    )
    await db_session.commit()

    created = await client.post(
        f"/api/projects/{project.id}/todos",
        json={"title": "Complete drawings", "assignee_id": collaborator.id},
        headers=auth_headers,
    )
    todo_id = created.json()["id"]

    resp = await client.patch(
        f"/api/projects/{project.id}/todos/{todo_id}",
        json={"status": "complete"},
        headers=collab_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "complete"


async def test_reassign_notifies_new_assignee(
    client: AsyncClient, auth_headers, project, collaborator, db_session
):
    db_session.add(
        ProjectMember(project_id=project.id, user_id=collaborator.id, role="collaborator")
    )
    await db_session.commit()

    created = await client.post(
        f"/api/projects/{project.id}/todos",
        json={"title": "Reassignable"},
        headers=auth_headers,
    )
    todo_id = created.json()["id"]

    resp = await client.patch(
        f"/api/projects/{project.id}/todos/{todo_id}",
        json={"assignee_id": collaborator.id},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["assignee"]["id"] == collaborator.id

    notif_result = await db_session.execute(
        select(Notification).where(
            Notification.user_id == collaborator.id,
            Notification.type == NotificationType.todo_assigned,
        )
    )
    assert notif_result.scalar_one_or_none() is not None


async def test_assign_non_internal_member_rejected(
    client: AsyncClient, auth_headers, project, db_session
):
    from src.models.user import User

    outsider = User(
        email="outsider@test.com",
        name="Outsider",
        hashed_password="x",
        role="architect",
        is_verified=True,
    )
    db_session.add(outsider)
    await db_session.commit()
    await db_session.refresh(outsider)

    resp = await client.post(
        f"/api/projects/{project.id}/todos",
        json={"title": "Bad assignee", "assignee_id": outsider.id},
        headers=auth_headers,
    )
    assert resp.status_code == 400


async def test_invalid_status_rejected(client: AsyncClient, auth_headers, project):
    created = await client.post(
        f"/api/projects/{project.id}/todos", json={"title": "X"}, headers=auth_headers
    )
    todo_id = created.json()["id"]
    resp = await client.patch(
        f"/api/projects/{project.id}/todos/{todo_id}",
        json={"status": "done"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


async def test_client_cannot_access_todos(client: AsyncClient, client_auth_headers, project):
    listing = await client.get(f"/api/projects/{project.id}/todos", headers=client_auth_headers)
    assert listing.status_code == 404

    create = await client.post(
        f"/api/projects/{project.id}/todos",
        json={"title": "Hidden"},
        headers=client_auth_headers,
    )
    assert create.status_code == 404


async def test_delete_todo(client: AsyncClient, auth_headers, project):
    created = await client.post(
        f"/api/projects/{project.id}/todos", json={"title": "Doomed"}, headers=auth_headers
    )
    todo_id = created.json()["id"]
    resp = await client.delete(f"/api/projects/{project.id}/todos/{todo_id}", headers=auth_headers)
    assert resp.status_code == 204

    listing = await client.get(f"/api/projects/{project.id}/todos", headers=auth_headers)
    assert all(t["id"] != todo_id for t in listing.json())
