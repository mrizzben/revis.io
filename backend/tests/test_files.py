"""Tests for file routes, focused on the PATCH /files/{file_id} milestone reassignment."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.models.file import DesignFile, ThumbnailStatus
from src.models.milestone import Milestone
from src.models.project import Project


def _make_file(project_id: int, uploaded_by_id: int, milestone_id: int | None) -> DesignFile:
    return DesignFile(
        id=uuid.uuid4(),
        project_id=project_id,
        milestone_id=milestone_id,
        uploaded_by_id=uploaded_by_id,
        filename="drawing.pdf",
        file_type="pdf",
        content_type="application/pdf",
        file_size=1024,
        s3_key=f"projects/{project_id}/{uuid.uuid4()}.pdf",
        thumbnail_status=ThumbnailStatus.pending,
    )


@pytest.fixture
async def project(db_session, test_architect, test_firm):
    proj = Project(name="Test Project", owner_id=test_architect.id, firm_id=test_firm.id)
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


@pytest.fixture
async def milestones(db_session, project):
    m1 = Milestone(project_id=project.id, name="Phase 1", position=0)
    m2 = Milestone(project_id=project.id, name="Phase 2", position=1)
    db_session.add_all([m1, m2])
    await db_session.commit()
    await db_session.refresh(m1)
    await db_session.refresh(m2)
    return m1, m2


@pytest.fixture
async def file(db_session, project, milestones, test_architect):
    f = _make_file(project.id, test_architect.id, milestones[0].id)
    db_session.add(f)
    await db_session.commit()
    await db_session.refresh(f)
    return f


async def test_architect_moves_file_between_milestones(
    client: AsyncClient, auth_headers, project, milestones, file
):
    resp = await client.patch(
        f"/api/files/{file.id}",
        json={"milestone_id": milestones[1].id},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["milestone_id"] == milestones[1].id
    assert body["id"] == str(file.id)


async def test_architect_moves_file_to_uncategorized(
    client: AsyncClient, auth_headers, project, file
):
    resp = await client.patch(
        f"/api/files/{file.id}", json={"milestone_id": None}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["milestone_id"] is None


async def test_rejects_milestone_from_another_project(
    client: AsyncClient, auth_headers, project, milestones, file, db_session
):
    file_id = file.id
    other_project = Project(name="Other Project", owner_id=1)
    db_session.add(other_project)
    await db_session.commit()
    await db_session.refresh(other_project)
    foreign_milestone = Milestone(project_id=other_project.id, name="Foreign")
    db_session.add(foreign_milestone)
    await db_session.commit()
    await db_session.refresh(foreign_milestone)

    resp = await client.patch(
        f"/api/files/{file_id}",
        json={"milestone_id": foreign_milestone.id},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    # File unchanged (endpoint must reject before writing)
    row = await db_session.execute(select(DesignFile.milestone_id).where(DesignFile.id == file_id))
    assert row.scalar_one() == milestones[0].id


async def test_client_cannot_reassign(
    client: AsyncClient, client_auth_headers, project, milestones, file
):
    resp = await client.patch(
        f"/api/files/{file.id}",
        json={"milestone_id": milestones[1].id},
        headers=client_auth_headers,
    )
    assert resp.status_code == 403


async def test_requires_authentication(client: AsyncClient, project, file):
    resp = await client.patch(f"/api/files/{file.id}", json={"milestone_id": None})
    assert resp.status_code == 401


async def test_file_not_found(client: AsyncClient, auth_headers):
    resp = await client.patch(
        f"/api/files/{uuid.uuid4()}", json={"milestone_id": None}, headers=auth_headers
    )
    assert resp.status_code == 404
