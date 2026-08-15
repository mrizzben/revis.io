"""Tests for T3 — review workflow."""


import pytest
from sqlalchemy import select

from src.models.project import Project, ProjectMember
from src.models.user import User


@pytest.fixture
async def project(db_session, test_architect, test_firm):
    proj = Project(name="Review Project", owner_id=test_architect.id, firm_id=test_firm.id)
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


@pytest.fixture
async def collaborator(db_session, project):
    user = User(
        email="collab@test.com",
        name="Collab",
        hashed_password="x",
        role="architect",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    member = ProjectMember(project_id=project.id, user_id=user.id, role="collaborator")
    db_session.add(member)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def collaborator_headers(collaborator):
    from src.core.security import create_access_token

    token = create_access_token(subject=collaborator.id, role="architect", firm_id=None)
    return {"Authorization": f"Bearer {token}"}


async def test_request_review_assigns_reviewer(
    client, auth_headers, project, test_architect, collaborator, seed_file
):
    file, version = await seed_file(project.id, test_architect.id)

    resp = await client.post(
        f"/api/files/{file.id}/reviews",
        json={"reviewer_id": collaborator.id, "revision_id": version.id},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "draft"
    assert body["reviewer"]["name"] == "Collab"
    assert body["requested_by"]["name"] == "Test Architect"
    assert body["revision_number"] == 1


async def test_reviewer_can_start_approve_and_record_decision(
    client, auth_headers, collaborator_headers, project, test_architect, collaborator, seed_file
):
    file, version = await seed_file(project.id, test_architect.id)
    created = (await client.post(
        f"/api/files/{file.id}/reviews",
        json={"reviewer_id": collaborator.id, "revision_id": version.id},
        headers=auth_headers,
    )).json()
    rid = created["id"]

    start = await client.post(f"/api/reviews/{rid}/transition", json={"action": "start"}, headers=collaborator_headers)
    assert start.status_code == 200
    assert start.json()["status"] == "in_review"

    approve = await client.post(
        f"/api/reviews/{rid}/transition",
        json={"action": "approve", "comment": "Looks good"},
        headers=collaborator_headers,
    )
    assert approve.status_code == 200
    body = approve.json()
    assert body["status"] == "approved"
    assert body["decision_comment"] == "Looks good"
    assert body["decided_by"]["name"] == "Collab"
    assert body["decided_at"] is not None


async def test_request_changes_flow(
    client, auth_headers, collaborator_headers, project, test_architect, collaborator, seed_file
):
    file, version = await seed_file(project.id, test_architect.id)
    rid = (await client.post(
        f"/api/files/{file.id}/reviews",
        json={"reviewer_id": collaborator.id, "revision_id": version.id},
        headers=auth_headers,
    )).json()["id"]

    await client.post(f"/api/reviews/{rid}/transition", json={"action": "start"}, headers=collaborator_headers)
    resp = await client.post(
        f"/api/reviews/{rid}/transition",
        json={"action": "request_changes", "comment": "Fix section A"},
        headers=collaborator_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "changes_requested"

    # Reviewer can restart after changes.
    resp = await client.post(f"/api/reviews/{rid}/transition", json={"action": "start"}, headers=collaborator_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_review"


async def test_client_cannot_see_internal_reviews(
    client, auth_headers, client_auth_headers, project, test_architect, collaborator, seed_file, db_session
):
    """A client with project access must still get 404 for an internal review
    and never see it in the reviews list."""
    from src.models.project import ProjectMember as PM

    client_user = (await db_session.execute(
        select(User).where(User.email == "client@test.com")
    )).scalar_one()
    db_session.add(PM(project_id=project.id, user_id=client_user.id, role="client"))
    await db_session.commit()

    file, version = await seed_file(project.id, test_architect.id)
    internal_id = (await client.post(
        f"/api/files/{file.id}/reviews",
        json={"reviewer_id": collaborator.id, "revision_id": version.id},
        headers=auth_headers,
    )).json()["id"]

    reviews = (await client.get(f"/api/files/{file.id}/reviews", headers=client_auth_headers)).json()
    ids = [r["id"] for r in reviews]
    assert internal_id not in ids

    # Client cannot transition an internal review.
    resp = await client.post(
        f"/api/reviews/{internal_id}/transition",
        json={"action": "approve"},
        headers=client_auth_headers,
    )
    assert resp.status_code == 404


async def test_client_review_visible_only_when_opened(
    client, auth_headers, client_auth_headers, project, test_architect, collaborator, seed_file, db_session
):
    from src.models.project import ProjectMember as PM

    client_user = (await db_session.execute(
        select(User).where(User.email == "client@test.com")
    )).scalar_one()
    db_session.add(PM(project_id=project.id, user_id=client_user.id, role="client"))
    await db_session.commit()

    file, version = await seed_file(project.id, test_architect.id)
    # Internal review (not opened to client).
    internal_id = (await client.post(
        f"/api/files/{file.id}/reviews",
        json={"reviewer_id": collaborator.id, "revision_id": version.id},
        headers=auth_headers,
    )).json()["id"]

    # Client review.
    opened_id = (await client.post(
        f"/api/files/{file.id}/reviews",
        json={"reviewer_id": collaborator.id, "revision_id": version.id, "is_client_review": True},
        headers=auth_headers,
    )).json()["id"]

    reviews = (await client.get(f"/api/files/{file.id}/reviews", headers=client_auth_headers)).json()
    ids = [r["id"] for r in reviews]
    assert opened_id in ids
    assert internal_id not in ids


async def test_review_history_recorded_in_activity(
    client, auth_headers, collaborator_headers, project, test_architect, collaborator, seed_file
):
    file, version = await seed_file(project.id, test_architect.id)
    rid = (await client.post(
        f"/api/files/{file.id}/reviews",
        json={"reviewer_id": collaborator.id, "revision_id": version.id},
        headers=auth_headers,
    )).json()["id"]
    await client.post(f"/api/reviews/{rid}/transition", json={"action": "start"}, headers=collaborator_headers)
    await client.post(
        f"/api/reviews/{rid}/transition", json={"action": "approve", "comment": "OK"}, headers=collaborator_headers
    )

    events = (await client.get(f"/api/projects/{project.id}/activity", headers=auth_headers)).json()
    types = [e["event_type"] for e in events]
    assert "review_requested" in types
    assert "review_approved" in types
