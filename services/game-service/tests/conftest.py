from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
from typing import AsyncGenerator
from unittest.mock import AsyncMock
import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.clients import wallet_client
from app.core.config import settings
from app.core.database import Base
from app.main import app

TEST_DB_FILE = "./test_game.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_FILE}"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def create_test_token(user_id: int, username: str, role: str = "player") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def mock_wallet(monkeypatch):
    """Mock wallet client to simulate Wallet Service responses."""
    mock_hold = AsyncMock(return_value={"status": "ok", "balance": "90000.00", "locked": "10000.00"})
    mock_settle = AsyncMock(return_value={"status": "ok", "balance": "110000.00", "locked": "0.00"})
    monkeypatch.setattr(wallet_client, "hold_bet", mock_hold)
    monkeypatch.setattr(wallet_client, "settle_bet", mock_settle)
    return {"hold": mock_hold, "settle": mock_settle}


@pytest.fixture
def player1_token() -> str:
    return create_test_token(user_id=1, username="player_one")


@pytest.fixture
def player2_token() -> str:
    return create_test_token(user_id=2, username="player_two")


@pytest.fixture
def admin_token() -> str:
    return create_test_token(user_id=999, username="admin_master", role="admin")

