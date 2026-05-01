from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py lives at backend/app/core/ — project root is three levels up
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "Where To Go"
    debug: bool = False

    # Database
    database_url: str

    # Auth
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 h

    # LLM — provider selection
    primary_provider: str = "groq"    # "groq" | "gemini"
    enable_cost_demo: bool = False     # route one call through Gemini for comparison

    # Groq (primary — free tier)
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # Gemini (fallback / cost-demo)
    gemini_api_key: str = ""

    # Model configuration
    cheap_model: str = "llama-3.1-8b-instant"      # Groq tier-1: ultra-fast
    strong_model: str = "llama-3.3-70b-versatile"  # Groq tier-2: smart
    demo_model: str = "gemini-1.5-flash"            # Gemini tier-3: cost demo

    # Theoretical pricing (per 1M tokens) — Groq free-tier, costs are theoretical
    groq_cheap_input_price: float = 0.05
    groq_cheap_output_price: float = 0.08
    groq_strong_input_price: float = 0.27
    groq_strong_output_price: float = 0.27
    # Gemini flash — actual cost
    gemini_flash_input_price: float = 0.075
    gemini_flash_output_price: float = 0.30

    # Optional fallbacks (not required for core functionality)
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Embeddings
    # "local" uses sentence-transformers/all-mpnet-base-v2 (no API key, matches ingest script)
    # "gemini" uses text-embedding-004 (requires GEMINI_API_KEY)
    # "openai" uses text-embedding-3-small (requires OPENAI_API_KEY)
    embedding_provider: str = "local"
    embedding_model: str = "all-mpnet-base-v2"
    embedding_dim: int = 768

    # ML
    ml_model_path: str = "ml/models/travel_style_classifier.joblib"

    # RAG
    rag_chunk_size: int = 512
    rag_chunk_overlap: int = 50
    rag_top_k: int = 5

    # Webhook
    webhook_url: str = ""
    webhook_timeout: int = 10

    # Discord (optional — set to fire notifications on every agent run)
    discord_webhook_url: str | None = None

    # AviationStack (route search — free 100 req/month: https://aviationstack.com)
    aviationstack_api_key: str = ""

    # LangSmith tracing (optional — set LANGCHAIN_API_KEY to enable)
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "where-to-go"

    # External APIs
    weather_api_key: str = ""

    # CORS — JSON list in .env: CORS_ORIGINS=["http://localhost:5173"]
    cors_origins: list[str] = ["http://localhost:5173"]

    # Test database (override via TEST_DATABASE_URL in .env or CI environment)
    test_database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/where_to_go_test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
