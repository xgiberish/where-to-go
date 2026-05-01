import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from unittest.mock import AsyncMock, MagicMock

from app.main import app
from app.core.config import get_settings
from app.db.models import Base
from app.dependencies import get_db, get_embedding_service, get_ml_service
from app.services.llm_service import LLMResponse

_settings = get_settings()


def _make_engine():
    return create_async_engine(_settings.test_database_url, echo=False)


# ── Database setup ─────────────────────────────────────────────────────────────
# create_tables is SYNC and uses asyncio.run() so it never binds asyncpg
# connections to any particular event loop — tests create their own engines
# in their own function-scoped loops, avoiding "Future attached to different loop".

@pytest.fixture(scope="session", autouse=True)
def create_tables():
    async def _create():
        engine = _make_engine()
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def _drop():
        engine = _make_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_create())
    yield
    asyncio.run(_drop())


@pytest_asyncio.fixture
async def db_session():
    engine = _make_engine()
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    engine = _make_engine()
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    # Lifespan does not run under ASGITransport, so app.state is never populated.
    # Override the two state-reading dependencies with in-process fakes.
    fake_embedding = MagicMock()
    fake_embedding.embed = AsyncMock(return_value=[0.0] * _settings.embedding_dim)

    fake_ml = MagicMock()
    fake_ml.predict = MagicMock(return_value=["adventure"])
    fake_ml.is_ready = True

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_embedding_service] = lambda: fake_embedding
    app.dependency_overrides[get_ml_service] = lambda: fake_ml

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


# ── LLM fixture ───────────────────────────────────────────────────────────────

@pytest.fixture
def mock_llm_client():
    """Drop-in AsyncMock replacement for LLMService."""
    mock = MagicMock()
    mock.cheap_call = AsyncMock(
        return_value=LLMResponse(
            content="Here is a quick destination summary.",
            provider="groq",
            model="llama-3.1-8b-instant",
            input_tokens=50,
            output_tokens=30,
            is_free_tier=True,
            tier="cheap",
            call_type="other",
        )
    )
    mock.strong_call = AsyncMock(
        return_value=LLMResponse(
            content="Here is your detailed 7-day itinerary.",
            provider="groq",
            model="llama-3.3-70b-versatile",
            input_tokens=120,
            output_tokens=200,
            is_free_tier=True,
            tier="strong",
            call_type="synthesis",
        )
    )
    return mock


# ── ML fixture ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_ml_model():
    """Mock sklearn Pipeline: .predict(X) returns ['adventure'] by default."""
    model = MagicMock()
    model.predict = MagicMock(return_value=["adventure"])
    return model


# ── Embedding fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def mock_embedding_service():
    """Mock EmbeddingService whose embed() returns a 768-dim zero vector."""
    mock = MagicMock()
    mock.embed = AsyncMock(return_value=[0.0] * _settings.embedding_dim)
    return mock


@pytest.fixture
def mock_embedding_model():
    """Mock AsyncOpenAI client whose embeddings.create returns a 768-dim vector."""
    vector = [0.01 * (i % 100) for i in range(_settings.embedding_dim)]

    data_item = MagicMock()
    data_item.embedding = vector

    response = MagicMock()
    response.data = [data_item]

    embeddings = MagicMock()
    embeddings.create = AsyncMock(return_value=response)

    openai_client = MagicMock()
    openai_client.embeddings = embeddings

    return openai_client


# ── Sample data fixture ───────────────────────────────────────────────────────

@pytest.fixture
def sample_destination_data():
    """Feature dict matching the expected ML pipeline input schema."""
    return {
        "name": "Bali",
        "country": "Indonesia",
        "climate": "tropical",
        "travel_style": "relaxation",
        "budget_tier": "mid",
        "best_season": "April-October",
        "tags": "beach,culture,yoga",
    }
