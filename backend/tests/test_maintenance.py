"""Tests for T8 — scheduled/on-demand storage maintenance orchestration."""

from datetime import UTC, datetime, timedelta

import pytest

from src.core.config import settings
from src.models.file import DesignFile
from src.services import maintenance as maintenance_service


@pytest.fixture
async def project(db_session, test_architect, test_firm):
    from src.models.project import Project

    proj = Project(name="Maintenance Project", owner_id=test_architect.id, firm_id=test_firm.id)
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


async def test_run_maintenance_aborts_abandoned_multipart(
    db_session, project, test_architect, seed_file, fake_s3
):
    await seed_file(project.id, test_architect.id)
    old = datetime.now(UTC) - timedelta(days=30)
    fake_s3.multipart.append({"Key": "uploads/abandoned.bin", "UploadId": "up-1", "Initiated": old})

    report = await maintenance_service.run_maintenance(db_session)

    assert report["aborted_multipart_uploads"] == 1
    assert report["purged_soft_deleted_files"] == 0
    assert report["errors"] == []
    assert fake_s3.multipart == []


async def test_run_maintenance_collects_abort_errors(
    db_session, project, test_architect, seed_file, fake_s3, monkeypatch
):
    await seed_file(project.id, test_architect.id)
    old = datetime.now(UTC) - timedelta(days=30)
    fake_s3.multipart.append({"Key": "uploads/abandoned.bin", "UploadId": "up-1", "Initiated": old})

    def _fail_abort(*args, **kwargs):
        raise RuntimeError("s3 explode")

    monkeypatch.setattr(fake_s3, "abort_multipart_upload", _fail_abort)

    report = await maintenance_service.run_maintenance(db_session)

    assert report["aborted_multipart_uploads"] == 0
    assert len(report["errors"]) == 1
    assert "up-1" in report["errors"][0]


async def test_run_maintenance_purges_expired_soft_deleted(
    db_session, project, test_architect, seed_file, fake_s3
):
    file, version = await seed_file(project.id, test_architect.id)
    file.is_deleted = True
    file.updated_at = datetime.now(UTC) - timedelta(days=60)
    await db_session.commit()

    report = await maintenance_service.run_maintenance(db_session)

    assert report["purged_soft_deleted_files"] == 1
    assert file.s3_key in fake_s3.deleted
    assert await db_session.get(DesignFile, file.id) is None


async def test_run_maintenance_keeps_recent_soft_deleted(
    db_session, project, test_architect, seed_file, fake_s3
):
    file, _ = await seed_file(project.id, test_architect.id)
    file.is_deleted = True
    # Default retention is 30 days; a fresh soft-delete must survive.
    await db_session.commit()

    report = await maintenance_service.run_maintenance(db_session)

    assert report["purged_soft_deleted_files"] == 0
    assert await db_session.get(DesignFile, file.id) is not None


async def test_maintenance_route_requires_firm_admin(client, db_session, test_firm):
    from src.core.security import create_access_token
    from src.models.user import User

    non_admin = User(
        email="draft@test.com",
        name="Draft Architect",
        hashed_password="x",
        role="architect",
        is_verified=True,
        firm_id=test_firm.id,
        is_firm_admin=False,
    )
    db_session.add(non_admin)
    await db_session.commit()
    await db_session.refresh(non_admin)
    token = create_access_token(subject=non_admin.id, role="architect", firm_id=non_admin.firm_id)

    resp = await client.post(
        "/api/storage/maintenance", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


async def test_maintenance_route_delegates_for_firm_admin(
    client, db_session, auth_headers, project, test_architect, seed_file, fake_s3
):
    await seed_file(project.id, test_architect.id)
    old = datetime.now(UTC) - timedelta(days=30)
    fake_s3.multipart.append({"Key": "uploads/abandoned.bin", "UploadId": "up-2", "Initiated": old})

    resp = await client.post("/api/storage/maintenance", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["aborted_multipart_uploads"] == 1
    assert body["purged_soft_deleted_files"] == 0
    assert body["retention_window_days"] == settings.MULTIPART_ABANDON_AFTER_SECONDS // 86400
    assert fake_s3.multipart == []
