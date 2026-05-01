"""Verify RAG setup: document counts, embedding presence, and retrieval quality.

Usage:
    python backend/scripts/verify_rag.py

Exit codes:
    0  — all checks passed
    1  — one or more checks failed
"""
import asyncio
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models import AgentRun, Embedding, ToolCall
from app.db.repositories.embedding_repo import EmbeddingRepository
from app.services.embedding_service import EmbeddingService

import structlog

log = structlog.get_logger()

# Queries that should return results — covers 3 of the 15 indexed destinations
_TEST_QUERIES = [
    ("temples and ancient ruins in Asia", "Kyoto"),
    ("beach scuba diving snorkelling", "Bali"),
    ("trekking mountains Himalayas base camp", "Kathmandu"),
]


async def verify() -> bool:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    passed = True

    async with SessionLocal() as session:

        # ── 1. Embedding counts ───────────────────────────────────────────────
        total_chunks = (
            await session.execute(select(func.count(Embedding.id)))
        ).scalar_one()

        total_with_vec = (
            await session.execute(
                select(func.count(Embedding.id)).where(Embedding.embedding.is_not(None))
            )
        ).scalar_one()

        distinct_dests = (
            await session.execute(
                select(func.count(distinct(Embedding.destination)))
            )
        ).scalar_one()

        print("── Embedding storage ─────────────────────────────────────────")
        print(f"  Total chunks stored   : {total_chunks}")
        print(f"  Chunks with vectors   : {total_with_vec}")
        print(f"  Distinct destinations : {distinct_dests}")

        if total_chunks == 0:
            print("  FAIL: No embeddings found. Run ingest_rag_data.py first.")
            passed = False
        elif total_with_vec < total_chunks:
            print(f"  WARN: {total_chunks - total_with_vec} chunks missing vectors.")
        else:
            print("  OK")

        # ── 2. Agent run persistence ──────────────────────────────────────────
        run_count = (
            await session.execute(select(func.count(AgentRun.id)))
        ).scalar_one()
        tool_call_count = (
            await session.execute(select(func.count(ToolCall.id)))
        ).scalar_one()

        print("\n── Persistence ───────────────────────────────────────────────")
        print(f"  Agent runs logged     : {run_count}")
        print(f"  Tool calls logged     : {tool_call_count}")
        print("  OK")

        # ── 3. Retrieval quality ──────────────────────────────────────────────
        print("\n── Retrieval quality ─────────────────────────────────────────")

        if total_chunks == 0:
            print("  SKIP: no embeddings to search.")
        else:
            embedding_service = EmbeddingService(settings)
            repo = EmbeddingRepository(session)

            for query, expected_dest in _TEST_QUERIES:
                query_vec = await embedding_service.embed(query)
                hits = await repo.similarity_search(query_vec, top_k=3)

                top_dests = [h.destination for h, _ in hits]
                top_scores = [round(1.0 - d, 3) for _, d in hits]
                hit = expected_dest in top_dests

                status = "OK  " if hit else "MISS"
                print(
                    f"  [{status}] '{query[:45]}'"
                    f"\n         top-3: {top_dests}  scores: {top_scores}"
                )
                if not hit:
                    passed = False

    await engine.dispose()

    print("\n── Summary ───────────────────────────────────────────────────")
    if passed:
        print("  All checks passed.")
    else:
        print("  One or more checks FAILED. See output above.")

    return passed


if __name__ == "__main__":
    ok = asyncio.run(verify())
    sys.exit(0 if ok else 1)
