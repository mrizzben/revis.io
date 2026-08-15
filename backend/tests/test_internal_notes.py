"""Tests for internal notes: create, reply, @mention fan-out, visibility."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.models.internal_note import InternalNote
from src.models.notification import Notification, NotificationType
from src.models.project import Project, ProjectMember


@pytest.fixture
async def project(db_session, test_architect, test_firm):
    proj = Project(name="Notes Project", owner_id=test_architect.id, firm_id=test_firm.id)
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


@pytest.fixture
async def collaborator(db_session, test_firm):
    from src.models.user import User

    user = User(
        email="note-collab@test.com",
        name="Note Collab",
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


async def test_owner_creates_note_with_mention(
    client: AsyncClient, auth_headers, project, collaborator, db_session
):
    # Ensure mentioned user is a collaborator
    db_session.add(
        ProjectMember(project_id=project.id, user_id=collaborator.id, role="collaborator")
    )
    await db_session.commit()

    resp = await client.post(
        f"/api/projects/{project.id}/internal-notes",
        json={"body": "Remember to update the drawings @teammate", "mentions": [collaborator.id]},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["body"].startswith("Remember")
    assert any(m["user_id"] == collaborator.id for m in body["mentions"])

    # Mention notification created for the target
    notif_result = await db_session.execute(
        select(Notification).where(
            Notification.user_id == collaborator.id,
            Notification.type == NotificationType.mention,
        )
    )
    notif = notif_result.scalar_one_or_none()
    assert notif is not None
    assert notif.reference_id == body["id"]


async def test_create_mention_notifies_only_mentioned(
    client: AsyncClient, auth_headers, project, collaborator, db_session
):
    db_session.add(
        ProjectMember(project_id=project.id, user_id=collaborator.id, role="collaborator")
    )
    await db_session.commit()

    await client.post(
        f"/api/projects/{project.id}/internal-notes",
        json={"body": "note with mention", "mentions": [collaborator.id]},
        headers=auth_headers,
    )
    # Author (owner) must not get a mention notification
    notif_result = await db_session.execute(
        select(Notification).where(
            Notification.user_id == project.owner_id,
            Notification.type == NotificationType.mention,
        )
    )
    assert notif_result.scalar_one_or_none() is None


async def test_collaborator_creates_note_and_replies(
    client: AsyncClient, collab_headers, project, collaborator, db_session
):
    db_session.add(
        ProjectMember(project_id=project.id, user_id=collaborator.id, role="collaborator")
    )
    await db_session.commit()

    resp = await client.post(
        f"/api/projects/{project.id}/internal-notes",
        json={"body": "first note"},
        headers=collab_headers,
    )
    assert resp.status_code == 201
    note_id = resp.json()["id"]

    reply = await client.post(
        f"/api/projects/{project.id}/internal-notes/{note_id}/replies",
        json={"body": "totally agree"},
        headers=collab_headers,
    )
    assert reply.status_code == 201
    assert reply.json()["parent_id"] == note_id

    listing = await client.get(f"/api/projects/{project.id}/internal-notes", headers=collab_headers)
    assert listing.status_code == 200
    notes = listing.json()["notes"]
    assert len(notes) == 1
    assert len(notes[0]["replies"]) == 1


async def test_client_cannot_see_or_create_notes(client: AsyncClient, client_auth_headers, project):
    listing = await client.get(
        f"/api/projects/{project.id}/internal-notes", headers=client_auth_headers
    )
    assert listing.status_code == 404

    create = await client.post(
        f"/api/projects/{project.id}/internal-notes",
        json={"body": "hidden attempt"},
        headers=client_auth_headers,
    )
    assert create.status_code == 404


async def test_reply_to_foreign_note_rejected(
    client: AsyncClient, auth_headers, project, collaborator, db_session
):
    db_session.add(
        ProjectMember(project_id=project.id, user_id=collaborator.id, role="collaborator")
    )
    await db_session.commit()

    note = InternalNote(project_id=project.id, author_id=project.owner_id, body="note")
    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)

    other_project = Project(name="Other", owner_id=project.owner_id)
    db_session.add(other_project)
    await db_session.commit()
    await db_session.refresh(other_project)

    resp = await client.post(
        f"/api/projects/{other_project.id}/internal-notes/{note.id}/replies",
        json={"body": "cross-project"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


async def test_mention_of_non_collaborator_still_creates_note(
    client: AsyncClient, auth_headers, project
):
    # Mentioning a user who is not a collaborator: note is created, no crash.
    resp = await client.post(
        f"/api/projects/{project.id}/internal-notes",
        json={"body": "note", "mentions": [999999]},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["mentions"] == []
