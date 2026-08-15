"""Tests for T6 — activity / audit history."""

import uuid

import pytest

from src.models.project import Project, ProjectMember


@pytest.fixture
async def project(db_session, test_architect, test_firm):
    proj = Project(name="Activity Project", owner_id=test_architect.id, firm_id=test_firm.id)
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


@pytest.fixture
async def client_member(db_session, project, test_client_user):
    member = ProjectMember(project_id=project.id, user_id=test_client_user.id, role="client")
    db_session.add(member)
    await db_session.commit()
    return member


async def test_upload_and_issue_record_events(
    client, auth_headers, project, test_architect, seed_file, fake_s3
):
    file, _ = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    key = f"uploads/{uuid.uuid4()}/rev.pdf"
    fake_s3.objects[key] = b"%PDF-1.4 v2"
    await client.post(
        f"/api/files/{file.id}/upload-complete",
        params={"key": key},
        headers=auth_headers,
    )
    await client.post(f"/api/files/{file.id}/versions/1/issue", headers=auth_headers)

    events = (await client.get(f"/api/projects/{project.id}/activity", headers=auth_headers)).json()
    types = [e["event_type"] for e in events]
    assert "revision_created" in types
    assert "revision_issued" in types

    # Immutable: each event has actor + timestamp + payload.
    issued = next(e for e in events if e["event_type"] == "revision_issued")
    assert issued["actor"]["name"] == "Test Architect"
    assert issued["payload"]["version_number"] == 1
    assert issued["created_at"] is not None


async def test_client_timeline_excludes_internal_events(
    client, auth_headers, client_auth_headers, project, test_architect, seed_file, fake_s3, client_member
):
    file, _ = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    # Internal upload (no client visibility).
    key = f"uploads/{uuid.uuid4()}/rev.pdf"
    fake_s3.objects[key] = b"%PDF-1.4 v2"
    await client.post(
        f"/api/files/{file.id}/upload-complete",
        params={"key": key},
        headers=auth_headers,
    )
    # Issue v1 → client event.
    await client.post(f"/api/files/{file.id}/versions/1/issue", headers=auth_headers)

    events = (await client.get(f"/api/projects/{project.id}/activity", headers=client_auth_headers)).json()
    types = [e["event_type"] for e in events]
    assert "revision_issued" in types
    assert "revision_created" not in types


async def test_activity_filter_by_event_type(
    client, auth_headers, project, test_architect, seed_file, fake_s3
):
    file, _ = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    await client.post(f"/api/files/{file.id}/versions/1/issue", headers=auth_headers)

    events = (
        await client.get(
            f"/api/projects/{project.id}/activity",
            params={"event_type": "revision_issued"},
            headers=auth_headers,
        )
    ).json()
    assert all(e["event_type"] == "revision_issued" for e in events)
    assert len(events) == 1


async def test_milestone_change_records_event(
    client, auth_headers, project, test_architect, seed_file, db_session
):
    from src.models.milestone import Milestone

    m = Milestone(project_id=project.id, name="Phase 1", position=0)
    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)

    file, _ = await seed_file(project.id, test_architect.id)
    await client.patch(f"/api/files/{file.id}", json={"milestone_id": m.id}, headers=auth_headers)

    events = (await client.get(f"/api/projects/{project.id}/activity", headers=auth_headers)).json()
    assert any(e["event_type"] == "milestone_changed" for e in events)
