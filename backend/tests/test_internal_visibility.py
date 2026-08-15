"""Security-critical: internal collaboration content must NEVER leak to clients.

Every internal endpoint returns 404 for client-role users, and no internal
content (notes, replies, mentions, to-dos, collaborator names) appears in any
client-facing payload (project detail).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.models.internal_note import InternalNote
from src.models.project import Project, ProjectMember
from src.models.todo import ToDo
from src.models.user import User


@pytest.fixture
async def project(db_session, test_architect, test_firm):
    proj = Project(name="Visibility Project", owner_id=test_architect.id, firm_id=test_firm.id)
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


@pytest.fixture
async def collaborator(db_session, test_firm) -> User:
    user = User(
        email="vis-collab@test.com",
        name="Visibility Collab",
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
async def client_member(db_session, project, test_client_user):
    db_session.add(
        ProjectMember(
            project_id=project.id,
            user_id=test_client_user.id,
            role="client",
        )
    )
    await db_session.commit()
    return test_client_user


@pytest.fixture
async def populated_project(db_session, project, collaborator, test_architect) -> Project:
    """Project with internal content: collaborator, note+mention, todo."""
    db_session.add(
        ProjectMember(project_id=project.id, user_id=collaborator.id, role="collaborator")
    )
    note = InternalNote(
        project_id=project.id,
        author_id=test_architect.id,
        body="Secret internal decision",
    )
    db_session.add(note)
    db_session.add(ToDo(project_id=project.id, created_by=test_architect.id, title="Secret todo"))
    await db_session.commit()
    return project


async def test_client_gets_404_on_all_internal_endpoints(
    client: AsyncClient,
    client_auth_headers,
    populated_project,
    client_member,
):
    pid = populated_project.id
    endpoints = [
        ("GET", f"/api/projects/{pid}/collaborators"),
        ("POST", f"/api/projects/{pid}/collaborators"),
        ("DELETE", f"/api/projects/{pid}/collaborators/1"),
        ("GET", f"/api/projects/{pid}/internal-notes"),
        ("POST", f"/api/projects/{pid}/internal-notes"),
        ("POST", f"/api/projects/{pid}/internal-notes/1/replies"),
        ("GET", f"/api/projects/{pid}/todos"),
        ("POST", f"/api/projects/{pid}/todos"),
        ("PATCH", f"/api/projects/{pid}/todos/1"),
        ("DELETE", f"/api/projects/{pid}/todos/1"),
    ]
    for method, url in endpoints:
        resp = await client.request(
            method, url, json={} if method == "POST" else None, headers=client_auth_headers
        )
        assert resp.status_code == 404, f"{method} {url} returned {resp.status_code}"


async def test_client_project_payload_has_no_internal_content(
    client: AsyncClient,
    client_auth_headers,
    populated_project,
    client_member,
):
    resp = await client.get(f"/api/projects/{populated_project.id}", headers=client_auth_headers)
    assert resp.status_code == 200
    body = resp.json()

    text = str(body)
    assert "Secret internal decision" not in text
    assert "Secret todo" not in text
    assert "Visibility Collab" not in text
    assert "internal" not in text.lower() or "internal" not in [k.lower() for k in body.keys()]


async def test_owner_serialization_excludes_nothing_internal_from_client_view(
    client: AsyncClient,
    client_auth_headers,
    populated_project,
    client_member,
):
    """Collaborator object must not be present in client-facing project JSON."""
    resp = await client.get(f"/api/projects/{populated_project.id}", headers=client_auth_headers)
    body = resp.json()
    assert "collaborators" not in body
    assert "internal_notes" not in body
    assert "todos" not in body


async def test_internal_content_latency_within_10s(
    client: AsyncClient,
    auth_headers,
    project,
    collaborator,
    db_session,
):
    """SC-003/SC-005: mention + to-do assignment round-trips complete well inside 10s.

    Timed integration assertion: creating a mention and an assigned to-do must
    persist (and be readable back) within the 10-second real-time budget.
    """
    import time

    from src.models.notification import Notification, NotificationType
    from src.models.project import ProjectMember

    db_session.add(
        ProjectMember(project_id=project.id, user_id=collaborator.id, role="collaborator")
    )
    await db_session.commit()

    start = time.monotonic()

    note_resp = await client.post(
        f"/api/projects/{project.id}/internal-notes",
        json={"body": "latency note", "mentions": [collaborator.id]},
        headers=auth_headers,
    )
    assert note_resp.status_code == 201

    todo_resp = await client.post(
        f"/api/projects/{project.id}/todos",
        json={"title": "latency todo", "assignee_id": collaborator.id},
        headers=auth_headers,
    )
    assert todo_resp.status_code == 201

    notif = await db_session.execute(
        select(Notification).where(
            Notification.user_id == collaborator.id,
            Notification.type == NotificationType.mention,
        )
    )
    assert notif.scalar_one_or_none() is not None

    elapsed = time.monotonic() - start
    assert elapsed < 10.0, f"mention+todo round-trip took {elapsed:.2f}s (budget 10s)"
