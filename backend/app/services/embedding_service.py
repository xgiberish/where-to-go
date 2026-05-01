import asyncio

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import Settings

log = structlog.get_logger()


class EmbeddingService:
    """Dense vector embeddings for RAG.

    Providers:
      local  — sentence-transformers/all-mpnet-base-v2 (768-dim, no API key, DEFAULT)
               Uses asyncio.to_thread so model.encode() doesn't block the event loop.
      gemini — text-embedding-004 (768-dim, requires GEMINI_API_KEY)
      openai — text-embedding-3-small (1536-dim, requires OPENAI_API_KEY)

    IMPORTANT: the provider used at retrieval time MUST match the one used during
    ingestion. The ingest script (backend/scripts/ingest_rag_data.py) uses the
    local sentence-transformers model, so the default here is also "local".
    """

    def __init__(self, settings: Settings) -> None:
        self._provider = settings.embedding_provider
        self._model = settings.embedding_model
        self._dim = settings.embedding_dim

        if self._provider == "local":
            from sentence_transformers import SentenceTransformer
            self._local_model = SentenceTransformer(self._model)
            log.info("embedding_model_loaded", provider="local", model=self._model)
        elif self._provider == "gemini":
            from google import genai
            self._gemini = genai.Client(api_key=settings.gemini_api_key)
        else:
            from openai import AsyncOpenAI
            self._openai = AsyncOpenAI(api_key=settings.openai_api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def embed(self, text: str) -> list[float]:
        """Return a dense embedding vector for *text*."""
        if self._provider == "local":
            return await self._embed_local(text)
        if self._provider == "gemini":
            return await self._embed_gemini(text)
        return await self._embed_openai(text)

    async def _embed_local(self, text: str) -> list[float]:
        vec = await asyncio.to_thread(
            self._local_model.encode, text, normalize_embeddings=True
        )
        log.debug("embedding_created", provider="local", model=self._model, dim=len(vec))
        return vec.tolist()

    async def _embed_gemini(self, text: str) -> list[float]:
        result = await self._gemini.aio.models.embed_content(
            model=self._model,
            contents=text,
        )
        embedding = list(result.embeddings[0].values)
        log.debug("embedding_created", provider="gemini", model=self._model, dim=len(embedding))
        return embedding

    async def _embed_openai(self, text: str) -> list[float]:
        response = await self._openai.embeddings.create(model=self._model, input=text)
        embedding = response.data[0].embedding
        log.debug("embedding_created", provider="openai", model=self._model, dim=len(embedding))
        return embedding
