"""Tests for T8 — file integrity, dedupe, scanning, storage lifecycle."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.models.file import ScanStatus
from src.models.project import Project


@pytest.fixture
async def project(db_session, test_architect, test_firm):
    proj = Project(name="Storage Project", owner_id=test_architect.id, firm_id=test_firm.id)
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


async def test_upload_complete_records_hash_and_scan(
    client, auth_headers, project, test_architect, seed_file, fake_s3
):
    file, _ = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    key = f"uploads/{uuid.uuid4()}/rev.pdf"
    fake_s3.objects[key] = b"%PDF-1.4 v2"

    resp = await client.post(
        f"/api/files/{file.id}/upload-complete",
        params={"key": key},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    versions = (await client.get(f"/api/files/{file.id}/versions", headers=auth_headers)).json()
    v2 = versions[-1]
    import hashlib

    assert v2["content_hash"] == hashlib.sha256(b"%PDF-1.4 v2").hexdigest()
    assert v2["scan_status"] == "clean"


async def test_interrupted_upload_fails_clearly(
    client, auth_headers, project, test_architect, seed_file, fake_s3, engine
):
    file, _ = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    key = f"uploads/{uuid.uuid4()}/never-uploaded.pdf"
    # Do NOT register the object in fake_s3 → interrupted upload.

    resp = await client.post(
        f"/api/files/{file.id}/upload-complete",
        params={"key": key},
        headers=auth_headers,
    )
    assert resp.status_code == 409

    # No version recorded: production get_db rolls back the failed request.
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.models.file import FileVersion

    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as fresh:
        count = (await fresh.execute(
            select(func.count()).select_from(FileVersion).where(FileVersion.file_id == file.id)
        )).scalar()
    assert count == 1


async def test_duplicate_upload_reuses_existing_key(
    client, auth_headers, project, test_architect, seed_file, fake_s3, db_session
):
    file, _ = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    # Second item with identical content.
    import hashlib

    from src.models.file import DesignFile, ThumbnailStatus

    other = DesignFile(
        id=uuid.uuid4(),
        project_id=project.id,
        uploaded_by_id=test_architect.id,
        filename="copy.pdf",
        file_type="pdf",
        content_type="application/pdf",
        file_size=len(b"%PDF-1.4 v1"),
        s3_key=f"uploads/{project.id}/{uuid.uuid4()}/copy.pdf",
        thumbnail_status=ThumbnailStatus.pending,
    )
    db = db_session
    db.add(other)
    await db.flush()

    # Upload identical content to the second item.
    key = other.s3_key
    fake_s3.objects[key] = b"%PDF-1.4 v1"
    resp = await client.post(
        f"/api/files/{other.id}/upload-complete",
        params={"key": key},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    versions = (await client.get(f"/api/files/{other.id}/versions", headers=auth_headers)).json()
    v1 = versions[0]
    # Deduped: hash matches and the freshly uploaded object was removed.
    assert v1["content_hash"] == hashlib.sha256(b"%PDF-1.4 v1").hexdigest()
    assert key in fake_s3.deleted


async def test_issue_blocked_when_scan_infected(
    client, auth_headers, project, test_architect, seed_file, fake_s3, db_session
):
    file, version = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    from sqlalchemy import select

    from src.models.file import FileVersion

    row = (await db_session.execute(
        select(FileVersion).where(FileVersion.id == version.id)
    )).scalar_one()
    row.scan_status = ScanStatus.infected
    await db_session.commit()

    resp = await client.post(f"/api/files/{file.id}/versions/1/issue", headers=auth_headers)
    assert resp.status_code == 409
    assert "malware" in resp.json()["detail"].lower()


async def test_storage_usage_reports_bytes_by_project(
    client, auth_headers, project, test_architect, seed_file
):
    file, _ = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1 (13 bytes)")
    # seed content length 19
    resp = await client.get(
        f"/api/storage/usage?project_id={project.id}", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_id"] == project.id
    assert body["total_bytes"] >= 19
    assert body["revision_count"] == 1


async def test_orphans_lists_unreferenced_objects(
    client, auth_headers, project, test_architect, seed_file, fake_s3
):
    file, version = await seed_file(project.id, test_architect.id, content=b"%PDF-1.4 v1")
    fake_s3.objects["uploads/orphaned.pdf"] = b"orphan"

    resp = await client.get("/api/storage/orphans", headers=auth_headers)
    assert resp.status_code == 200
    assert "uploads/orphaned.pdf" in resp.json()["orphans"]


async def test_maintenance_aborts_abandoned_multipart(
    client, auth_headers, project, test_architect, seed_file, fake_s3
):
    file, _ = await seed_file(project.id, test_architect.id)
    old = datetime.now(UTC) - timedelta(days=30)
    fake_s3.multipart.append({"Key": "uploads/abandoned.bin", "UploadId": "up-1", "Initiated": old})

    resp = await client.post("/api/storage/maintenance", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["aborted_multipart_uploads"] == 1
    assert fake_s3.multipart == []
