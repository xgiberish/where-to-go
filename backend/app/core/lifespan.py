import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import engine
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.ml_service import MLService

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.debug)
    log.info("starting_up", app=settings.app_name, debug=settings.debug)

    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    log.info("database_connected")

    # EmbeddingService loads the sentence-transformers model from disk (~400MB for local
    # provider). Run in a thread so the event loop stays unblocked during startup.
    app.state.embedding_service = await asyncio.to_thread(EmbeddingService, settings)
    log.info("embedding_service_ready", provider=settings.embedding_provider, model=settings.embedding_model)

    # LLM service only initializes API clients (no local model, non-blocking)
    app.state.llm_service = LLMService(settings)
    log.info("llm_service_ready")

    # MLService loads the joblib classifier (~300KB, fast but still blocking I/O)
    app.state.ml_service = await asyncio.to_thread(MLService, settings.ml_model_path)
    log.info("ml_service_ready", model_loaded=app.state.ml_service.is_ready)

    yield

    log.info("shutting_down")
    await engine.dispose()
