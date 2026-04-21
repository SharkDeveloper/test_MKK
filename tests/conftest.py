"""
Test fixtures for payment processing service.
"""
import asyncio
import pytest
from typing import AsyncGenerator, Generator
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import create_app
from app.core.config import Settings


# Test settings with in-memory SQLite for fast unit tests
class TestSettings(Settings):
    @property
    def database_url(self) -> str:
        return "sqlite+aiosqlite:///:memory:"
    
    @property
    def sync_database_url(self) -> str:
        return "sqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session_maker = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
async def client(db_session) -> AsyncGenerator:
    """Create a test FastAPI client."""
    from httpx import AsyncClient, ASGITransport
    
    # Override the database dependency
    async def override_get_db():
        yield db_session
    
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_payment_data():
    """Sample payment data for testing."""
    return {
        "amount": "100.00",
        "currency": "RUB",
        "description": "Test payment",
        "metadata": {"order_id": "12345"},
        "webhook_url": "https://example.com/webhook",
    }


@pytest.fixture
def sample_idempotency_key() -> str:
    """Sample idempotency key for testing."""
    return "test-idempotency-key-12345"


@pytest.fixture
def api_key() -> str:
    """API key for authentication."""
    return "test-api-key-secret"
