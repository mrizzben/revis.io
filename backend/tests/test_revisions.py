"""Tests for T1 (file revisions), T2 (checkpoints/issuance), T7 (visibility)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from src.models.file import DesignFile, FileVersion, RevisionVisibility, ScanStatus, ThumbnailStatus
from src.models.milestone import Milestone
from src.models.project import Project, ProjectMember
from src.models.user import User
from src.services import file as file_service


@pytest.fixture
async def project(db_session, test_architect, test_firm):
    proj = Project(name="Revision Project", owner_id=test_architect.id, firm_id=test_firm.id)
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


async def _upload_revision(
    client: AsyncClient,
    auth_headers,
    file_id: str,
    fake_s3,
    content: bytes,
    key: str | None = None,
    message: str | None = None,
    name: str | None = None,
):
    key = key or f"uploads/{uuid.uuid4()}/revision.bin"
    fake_s3.objects[key] = content
    params = {"key": key}
    if message:
        params["revision_message"] = message
    if name:
        params["name"] = name
    resp = await client.post(
        f"/api/files/{file_id}/upload-complete", params=params, headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_second_upload_is_revision_2_of_same_item(
    client, auth_headers, project, test_architect, seed_file, fake_s3
):
    file, v1 = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")

    result = await _upload_revision(
        client, auth_headers, str(file.id), fake_s3, b"%PDF-1.4 v2", message="Added section B"
    )

    assert result["version_number"] == 2

    versions = (await client.get(f"/api/files/{file.id}/versions", headers=auth_headers)).json()
    assert [v["version_number"] for v in versions] == [1, 2]
    assert versions[-1]["revision_message"] == "Added section B"
    assert versions[-1]["visibility"] == "internal"
    assert versions[-1]["is_current"] is True
    # Stable identity preserved
    detail = (await client.get(f"/api/files/{file.id}", headers=auth_headers)).json()
    assert detail["id"] == str(file.id)
    assert detail["version_number"] == 2


async def test_restore_makes_prior_revision_current_without_deleting_history(
    client, auth_headers, project, test_architect, seed_file, fake_s3
):
    file, v1 = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    await _upload_revision(client, auth_headers, str(file.id), fake_s3, b"%PDF-1.4 v2")

    resp = await client.post(f"/api/files/{file.id}/versions/1/restore", headers=auth_headers)
    assert resp.status_code == 200

    versions = (await client.get(f"/api/files/{file.id}/versions", headers=auth_headers)).json()
    assert [v["version_number"] for v in versions] == [1, 2]
    assert versions[0]["is_current"] is True

    detail = (await client.get(f"/api/files/{file.id}", headers=auth_headers)).json()
    assert detail["version_number"] == 1


async def test_issue_marks_revision_client_issued_and_supersedes_previous(
    client, auth_headers, project, test_architect, seed_file, fake_s3, client_member
):
    file, v1 = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    await _upload_revision(client, auth_headers, str(file.id), fake_s3, b"%PDF-1.4 v2")

    r1 = await client.post(f"/api/files/{file.id}/versions/1/issue", headers=auth_headers)
    assert r1.status_code == 200
    assert r1.json()["visibility"] == "client_issued"
    assert r1.json()["issued_by"]["name"] == "Test Architect"

    r2 = await client.post(f"/api/files/{file.id}/versions/2/issue", headers=auth_headers)
    assert r2.status_code == 200

    versions = (await client.get(f"/api/files/{file.id}/versions", headers=auth_headers)).json()
    by_num = {v["version_number"]: v for v in versions}
    assert by_num[1]["visibility"] == "superseded"
    assert by_num[2]["visibility"] == "client_issued"


async def test_client_only_sees_issued_revisions(
    client,
    auth_headers,
    client_auth_headers,
    project,
    test_architect,
    seed_file,
    fake_s3,
    client_member,
):
    file, v1 = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    # Upload an internal revision — client must not see it at all.
    await _upload_revision(client, auth_headers, str(file.id), fake_s3, b"%PDF-1.4 v2-internal")

    files = (
        await client.get(f"/api/projects/{project.id}/files", headers=client_auth_headers)
    ).json()
    assert files == []

    detail = await client.get(f"/api/projects/{project.id}", headers=client_auth_headers)
    assert detail.status_code == 200
    assert detail.json()["files"] == []

    # Issue v1 → client sees only v1, current.
    await client.post(f"/api/files/{file.id}/versions/1/issue", headers=auth_headers)
    files = (
        await client.get(f"/api/projects/{project.id}/files", headers=client_auth_headers)
    ).json()
    assert len(files) == 1
    item = files[0]
    assert item["current_version"]["version_number"] == 1
    assert item["current_version"]["visibility"] == "client_issued"
    assert [v["version_number"] for v in item["versions"]] == [1]

    # Client cannot fetch the internal revision directly.
    r = await client.get(f"/api/files/{file.id}/versions/2", headers=client_auth_headers)
    assert r.status_code == 404
    r = await client.get(f"/api/files/{file.id}/versions/2/download", headers=client_auth_headers)
    assert r.status_code == 404


async def test_client_sees_latest_issued_as_current_even_after_internal_upload(
    client,
    auth_headers,
    client_auth_headers,
    project,
    test_architect,
    seed_file,
    fake_s3,
    client_member,
):
    file, v1 = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    await client.post(f"/api/files/{file.id}/versions/1/issue", headers=auth_headers)
    # Internal upload after issuing.
    await _upload_revision(client, auth_headers, str(file.id), fake_s3, b"%PDF-1.4 v2-internal")

    files = (
        await client.get(f"/api/projects/{project.id}/files", headers=client_auth_headers)
    ).json()
    assert files[0]["current_version"]["version_number"] == 1
    assert files[0]["version_number"] == 1


async def test_comments_preserved_and_scoped_to_revisions(
    client,
    auth_headers,
    client_auth_headers,
    project,
    test_architect,
    seed_file,
    fake_s3,
    client_member,
):
    file, v1 = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    await client.post(f"/api/files/{file.id}/versions/1/issue", headers=auth_headers)

    # All-revision comment (no version_id).
    r = await client.post(
        f"/api/files/{file.id}/comments",
        json={"body": "Applies everywhere"},
        headers=auth_headers,
    )
    assert r.status_code == 201

    # Revision-scoped comment (version 1).
    r = await client.post(
        f"/api/files/{file.id}/comments",
        json={"body": "About v1", "version_id": v1.id},
        headers=auth_headers,
    )
    assert r.status_code == 201

    # Upload v2 — comments must not be lost.
    await _upload_revision(client, auth_headers, str(file.id), fake_s3, b"%PDF-1.4 v2")
    comments = (await client.get(f"/api/files/{file.id}/comments", headers=auth_headers)).json()
    assert len(comments) == 2
    by_scope = {c["scope"]: c for c in comments}
    assert by_scope["all"]["body"] == "Applies everywhere"
    assert by_scope["revision"]["version_number"] == 1


async def test_checkpoint_naming_and_metadata(
    client, auth_headers, project, test_architect, seed_file, fake_s3
):
    file, v1 = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")

    resp = await client.patch(
        f"/api/files/{file.id}/versions/1",
        json={"name": "Planning submission", "description": "For the planning authority"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Planning submission"
    assert resp.json()["description"] == "For the planning authority"


async def test_archive_hides_from_normal_views(
    client, auth_headers, project, test_architect, seed_file, fake_s3
):
    file, v1 = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    await client.post(f"/api/files/{file.id}/versions/1/issue", headers=auth_headers)
    await _upload_revision(client, auth_headers, str(file.id), fake_s3, b"%PDF-1.4 v2")
    await client.post(f"/api/files/{file.id}/versions/2/issue", headers=auth_headers)

    r = await client.post(f"/api/files/{file.id}/versions/1/archive", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["visibility"] == "archived"

    versions = (await client.get(f"/api/files/{file.id}/versions", headers=auth_headers)).json()
    assert [v["version_number"] for v in versions] == [2]

    archived = (
        await client.get(
            f"/api/files/{file.id}/versions",
            params={"include_archived": "true"},
            headers=auth_headers,
        )
    ).json()
    assert {v["version_number"] for v in archived} == {1, 2}


async def test_client_cannot_issue_or_restore(
    client, client_auth_headers, project, test_architect, seed_file, fake_s3, client_member
):
    file, v1 = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    r = await client.post(f"/api/files/{file.id}/versions/1/issue", headers=client_auth_headers)
    assert r.status_code == 403
    r = await client.post(f"/api/files/{file.id}/versions/1/restore", headers=client_auth_headers)
    assert r.status_code == 403


async def test_revision_download_uses_issued_key_for_client(
    client,
    auth_headers,
    client_auth_headers,
    project,
    test_architect,
    seed_file,
    fake_s3,
    client_member,
):
    file, v1 = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    await client.post(f"/api/files/{file.id}/versions/1/issue", headers=auth_headers)
    await _upload_revision(client, auth_headers, str(file.id), fake_s3, b"%PDF-1.4 v2-internal")

    # Client download resolves to the issued revision's key.
    r = await client.get(
        f"/api/files/{file.id}/download", headers=client_auth_headers, follow_redirects=False
    )
    assert r.status_code == 302
    assert v1.s3_key in r.headers["location"]

    # Architect download resolves to the current (internal) revision key.
    r = await client.get(
        f"/api/files/{file.id}/download", headers=auth_headers, follow_redirects=False
    )
    assert r.status_code == 302
    assert "v2" in r.headers["location"] or "revision.bin" in r.headers["location"]


async def test_file_preview_returns_inline_url_without_redirect(
    client, auth_headers, project, test_architect, seed_file, fake_s3
):
    file, _ = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")

    response = await client.get(
        f"/api/files/{file.id}/download",
        params={"return_url": "true", "inline": "true"},
        headers=auth_headers,
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert response.json()["url"]


# ── T4 comparison ──────────────────────────────────────────


async def test_compare_supported_revisions(
    client, auth_headers, project, test_architect, seed_file, fake_s3
):
    file, v1 = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    await _upload_revision(client, auth_headers, str(file.id), fake_s3, b"%PDF-1.4 v2")

    resp = await client.post(
        f"/api/files/{file.id}/compare",
        json={"from_version": 1, "to_version": 2},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["supported"] is True
    assert body["from"]["version_number"] == 1
    assert body["to"]["version_number"] == 2
    assert body["from"]["download_url"] and body["to"]["download_url"]


async def test_compare_unsupported_format_explains_not_available(
    client, auth_headers, project, test_architect, db_session, fake_s3
):
    file = DesignFile(
        id=uuid.uuid4(),
        project_id=project.id,
        uploaded_by_id=test_architect.id,
        filename="plan.dwg",
        file_type="dwg",
        content_type="application/acad",
        file_size=5,
        s3_key=f"uploads/{project.id}/{uuid.uuid4()}/plan.dwg",
        thumbnail_status=ThumbnailStatus.unsupported,
    )
    db_session.add(file)
    await db_session.flush()
    v1 = FileVersion(
        file_id=file.id,
        version_number=1,
        s3_key=file.s3_key,
        file_size=5,
        uploaded_by_id=test_architect.id,
        visibility=RevisionVisibility.internal,
        scan_status=ScanStatus.clean,
    )
    v2 = FileVersion(
        file_id=file.id,
        version_number=2,
        s3_key=file.s3_key,
        file_size=5,
        uploaded_by_id=test_architect.id,
        visibility=RevisionVisibility.internal,
        scan_status=ScanStatus.clean,
    )
    db_session.add_all([v1, v2])
    await db_session.commit()

    resp = await client.post(
        f"/api/files/{file.id}/compare",
        json={"from_version": 1, "to_version": 2},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["supported"] is False
    assert body["explanation"] and "not available" in body["explanation"].lower()


async def test_client_cannot_compare_internal_revisions(
    client,
    auth_headers,
    client_auth_headers,
    project,
    test_architect,
    seed_file,
    fake_s3,
    client_member,
):
    file, v1 = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    await _upload_revision(client, auth_headers, str(file.id), fake_s3, b"%PDF-1.4 v2-internal")

    resp = await client.post(
        f"/api/files/{file.id}/compare",
        json={"from_version": 1, "to_version": 2},
        headers=client_auth_headers,
    )
    assert resp.status_code == 404


async def test_project_payload_survives_version_with_milestone(
    db_session, engine, project, test_architect
):
    """Regression: a version attached to a milestone must not break the file payload.

    build_version_payload used to lazy-load FileVersion.milestone, raising
    MissingGreenlet on a fresh session (production has one session per request)
    and 500ing GET /projects/{id} right after an upload into a milestone.
    """
    m = Milestone(project_id=project.id, name="Phase 1", position=0)
    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)

    f = DesignFile(
        id=uuid.uuid4(),
        project_id=project.id,
        milestone_id=m.id,
        uploaded_by_id=test_architect.id,
        filename="plan.pdf",
        file_type="pdf",
        content_type="application/pdf",
        file_size=13,
        s3_key=f"uploads/{project.id}/{uuid.uuid4()}/plan.pdf",
        thumbnail_status=ThumbnailStatus.pending,
    )
    db_session.add(f)
    await db_session.flush()
    v = FileVersion(
        file_id=f.id,
        version_number=1,
        s3_key=f.s3_key,
        file_size=13,
        uploaded_by_id=test_architect.id,
        visibility=RevisionVisibility.internal,
        scan_status=ScanStatus.clean,
        milestone_id=m.id,
    )
    db_session.add(v)
    await db_session.flush()
    f.current_version_id = v.id
    await db_session.commit()
    file_id = f.id

    # Fresh session, mirroring production's one-session-per-request. Load the
    # file the way the project-detail route does; the milestone is NOT in the
    # identity map, so a lazy load would raise MissingGreenlet.
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as fresh:
        file = (
            await fresh.execute(
                select(DesignFile)
                .options(
                    selectinload(DesignFile.uploaded_by), selectinload(DesignFile.design_option)
                )
                .where(DesignFile.id == file_id)
            )
        ).scalar_one()
        user = (await fresh.execute(select(User).where(User.id == test_architect.id))).scalar_one()

        payload = await file_service.build_file_payload(fresh, file, user)
        assert payload["current_version"]["milestone_name"] == "Phase 1"
