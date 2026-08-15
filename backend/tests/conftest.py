import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.database import get_db
from src.core.security import create_access_token, hash_password
from src.main import app
from src.models.base import Base
from src.models.user import Firm, User
from src.websocket import get_manager, set_manager
from src.websocket.manager import ProjectRoomManager

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def engine():
    if os.path.exists("./test.db"):
        os.remove("./test.db")
    test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


class _NoopWsManager(ProjectRoomManager):
    """Stand-in for ProjectRoomManager so routes don't require a running Redis."""

    async def broadcast_to_project(self, *args, **kwargs):
        return None

    async def broadcast_to_project_team(self, *args, **kwargs):
        return None


@pytest.fixture(autouse=True)
def _stub_ws_manager():
    original = get_manager()
    set_manager(_NoopWsManager())
    yield
    set_manager(original)


@pytest.fixture(autouse=True)
async def _clean_tables(engine):
    """Delete all committed fixture rows after each test.

    The db_session fixture only rolls back uncommitted work, but the data
    fixtures (test_firm, test_architect, ...) explicitly commit, so rows
    persist across function-scoped tests and collide on unique columns.
    """
    yield
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def test_firm(db_session) -> Firm:
    firm = Firm(name="Test Architecture Firm")
    db_session.add(firm)
    await db_session.commit()
    await db_session.refresh(firm)
    return firm


@pytest.fixture
async def test_architect(db_session, test_firm) -> User:
    user = User(
        email="architect@test.com",
        name="Test Architect",
        hashed_password=hash_password("password123"),
        role="architect",
        is_verified=True,
        firm_id=test_firm.id,
        is_firm_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_client_user(db_session) -> User:
    user = User(
        email="client@test.com",
        name="Test Client",
        hashed_password=hash_password("password123"),
        role="client",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_architect):
    token = create_access_token(
        subject=test_architect.id,
        role="architect",
        firm_id=test_architect.firm_id,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client_auth_headers(test_client_user):
    token = create_access_token(
        subject=test_client_user.id,
        role="client",
        firm_id=None,
    )
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════════════════
# Fake S3 (T1/T8): lets upload-complete and storage routes run without MinIO
# ═══════════════════════════════════════════════════════════

import hashlib

from src.models.file import RevisionVisibility, ScanStatus
from src.services import file as file_service


class FakeS3:
    """In-memory stand-in for the boto3 S3 client used by file service."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.multipart: list[dict] = []
        self.deleted: list[str] = []

    def put_object(self, Bucket: str, Key: str, Body: bytes | None = None, **kwargs) -> None:
        self.objects[Key] = Body if Body is not None else b""

    def head_object(self, Bucket: str, Key: str) -> dict:
        if Key not in self.objects:
            raise Exception(f"NoSuchKey: {Key}")
        return {"Key": Key}

    def get_object(self, Bucket: str, Key: str, Range: str | None = None) -> dict:
        if Key not in self.objects:
            raise Exception(f"NoSuchKey: {Key}")
        body = self.objects[Key]
        if Range and Range.startswith("bytes="):
            start = int(Range.split("=")[1].split("-")[0])
            body = body[start:]

        class _Body:
            def __init__(self, data: bytes) -> None:
                self._data = data
                self._offset = 0

            def read(self, size: int | None = None) -> bytes:
                if size is None:
                    chunk = self._data[self._offset:]
                    self._offset = len(self._data)
                    return chunk
                chunk = self._data[self._offset:self._offset + size]
                self._offset += len(chunk)
                return chunk

            def close(self) -> None:
                pass

        return {"Body": _Body(body)}

    def delete_object(self, Bucket: str, Key: str) -> None:
        self.objects.pop(Key, None)
        self.deleted.append(Key)

    def generate_presigned_url(self, operation: str, Params: dict | None = None, ExpiresIn: int = 3600) -> str:
        key = (Params or {}).get("Key", "object")
        bucket = (Params or {}).get("Bucket", "bucket")
        return f"https://s3.test/{bucket}/{key}?sig=fake&expires={ExpiresIn}"

    def abort_multipart_upload(self, Bucket: str, Key: str, UploadId: str) -> None:
        self.multipart = [m for m in self.multipart if m["UploadId"] != UploadId]

    def get_paginator(self, name: str):
        if name == "list_objects_v2":
            return FakePaginator(lambda Bucket=None, Prefix=None: {"Contents": [{"Key": k} for k in self.objects if Prefix is None or k.startswith(Prefix)]})
        if name == "list_multipart_uploads":
            return FakePaginator(lambda Bucket=None: {"Uploads": list(self.multipart)})
        raise ValueError(f"Unknown paginator {name}")


class FakePaginator:
    def __init__(self, fn) -> None:
        self._fn = fn

    def paginate(self, **kwargs):
        yield self._fn(**kwargs)


@pytest.fixture(autouse=True)
def fake_s3(monkeypatch):
    """Stand in for S3 + the S3-dependent integrity helpers."""
    store = FakeS3()

    def _get_client():
        return store

    monkeypatch.setattr(file_service, "_get_lazy_s3_client", _get_client)
    monkeypatch.setattr(file_service, "_get_lazy_presigned_s3_client", _get_client)

    def _object_exists(s3, bucket, key):
        return key in store.objects

    def _compute_hash(s3, bucket, key):
        return hashlib.sha256(store.objects.get(key, b"")).hexdigest()

    def _verify_mime(s3, bucket, key, file_type):
        return True

    def _scan(s3, bucket, key, file_size):
        return ScanStatus.clean

    monkeypatch.setattr(file_service, "object_exists", _object_exists)
    monkeypatch.setattr(file_service, "compute_object_hash", _compute_hash)
    monkeypatch.setattr(file_service, "verify_content_mime", _verify_mime)
    monkeypatch.setattr(file_service, "scan_object_with_clamd", _scan)
    return store


@pytest.fixture
def seed_file(db_session, fake_s3):
    """Create a design item with one completed revision and register its object."""
    from src.models.file import DesignFile, FileVersion, ThumbnailStatus

    async def _seed(project_id: int, uploaded_by_id: int, filename="drawing.pdf", content=b"%PDF-1.4 seed content") -> tuple[DesignFile, FileVersion]:
        file = DesignFile(
            id=uuid4(),
            project_id=project_id,
            uploaded_by_id=uploaded_by_id,
            filename=filename,
            file_type="pdf",
            content_type="application/pdf",
            file_size=len(content),
            s3_key=f"uploads/{project_id}/{uuid4()}/{filename}",
            thumbnail_status=ThumbnailStatus.pending,
        )
        db_session.add(file)
        await db_session.flush()
        version = FileVersion(
            file_id=file.id,
            version_number=1,
            s3_key=file.s3_key,
            file_size=len(content),
            uploaded_by_id=uploaded_by_id,
            content_hash=hashlib.sha256(content).hexdigest(),
            visibility=RevisionVisibility.internal,
            scan_status=ScanStatus.clean,
        )
        db_session.add(version)
        await db_session.flush()
        file.current_version_id = version.id
        fake_s3.objects[file.s3_key] = content
        await db_session.commit()
        await db_session.refresh(file)
        return file, version

    return _seed


from uuid import uuid4  # noqa: E402
