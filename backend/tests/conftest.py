import asyncio
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.main import app
from src.core.database import get_db
from src.core.security import create_access_token, hash_password
from src.models.base import Base
from src.models.user import Firm, User

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def engine():
    test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


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