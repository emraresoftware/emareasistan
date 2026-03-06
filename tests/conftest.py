"""
Test yapılandırması ve ortak fixture'lar.
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

# Proje kökünü sys.path'e ekle
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Test ortamı env değişkenleri
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test_asistan.db")
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session():
    """Her test için temiz veritabanı oturumu."""
    from models.database import AsyncSessionLocal, init_db
    await init_db()
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_client():
    """FastAPI test client'ı."""
    from httpx import AsyncClient, ASGITransport
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_tenant_data():
    """Örnek tenant verisi."""
    return {
        "name": "Test Firma",
        "slug": "test-firma",
        "status": "active",
    }


@pytest.fixture
def sample_user_data():
    """Örnek kullanıcı verisi."""
    return {
        "name": "Test User",
        "email": "test@example.com",
        "password": "test123456",
        "role": "admin",
    }
