"""
Retrieval quality test — runs 5 queries and prints ranked results.

Results are appended to backend/results/rag_retrieval_results.csv after each run,
matching the pattern of ml/results/experiment_results.csv.

Uses the same embedding model as ingest_rag_data.py (sentence-transformers
all-mpnet-base-v2) so vectors are comparable.

Usage:
    python backend/scripts/test_rag_retrieval.py
"""
import asyncio
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_PROJECT_ROOT = _BACKEND_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))
sys.path.insert(0, str(_PROJECT_ROOT))

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.services.embedding_service import EmbeddingService
from app.services.rag_service import RAGService

log = structlog.get_logger()

RESULTS_CSV = _BACKEND_DIR / "results" / "rag_retrieval_results.csv"
FIELDNAMES = [
    "timestamp", "query", "top_k",
    "top_1_dest", "top_1_score",
    "top_2_dest", "top_2_score",
    "top_3_dest", "top_3_score",
    "confidence", "relevant", "notes",
]

TEST_QUERIES = [
    "hiking adventure",
    "quiet beach destinations",
    "cultural cities",
    "budget travel southeast asia",
    "budget beaches",
]

EXPECTED_HINTS = {
    "hiking adventure":              ["Pokhara", "Kathmandu", "Chiang Mai"],
    "quiet beach destinations":      ["Boracay", "Bali", "Penang"],
    "cultural cities":               ["Kyoto", "Hoi An", "Siem Reap", "Bangkok"],
    "budget travel southeast asia":  ["Hanoi", "Luang Prabang", "Chiang Mai"],
    "budget beaches":                ["Boracay", "Bali", "Penang"],
}


def _write_results(rows: list[dict]) -> None:
    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    write_header = not RESULTS_CSV.exists()
    with RESULTS_CSV.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)
    log.info("retrieval_results_written", path=str(RESULTS_CSV), rows=len(rows))


async def run_tests() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    embedding_service = EmbeddingService(settings)
    ts = datetime.now(timezone.utc).isoformat()

    async with SessionLocal() as session:
        rag_service = RAGService(session, embedding_service)

        print("\n=== RAG Retrieval Quality Test ===\n")

        csv_rows: list[dict] = []
        bad_retrievals: list[str] = []

        for query in TEST_QUERIES:
            result = await rag_service.retrieve(query, top_k=5)
            hints = EXPECTED_HINTS.get(query, [])

            print(f"Query: '{query}'")
            print(f"  confidence={result.confidence:.3f}  sources={result.sources}")

            for doc in result.documents:
                preview = doc.content[:120].replace("\n", " ")
                preview = preview.encode("ascii", errors="replace").decode("ascii")
                print(f"  [{doc.score:.3f}] {doc.destination}: {preview}...")

            top_sources = [s.lower() for s in result.sources[:3]]
            hit = any(h.lower() in top_sources for h in hints)
            if hints and not hit:
                flag = f"*** BAD: expected one of {hints} in top-3, got {result.sources[:3]}"
                print(f"  {flag}")
                bad_retrievals.append(f"'{query}': {flag}")
            print()

            docs = result.documents
            csv_rows.append({
                "timestamp": ts,
                "query": query,
                "top_k": 5,
                "top_1_dest": docs[0].destination if len(docs) > 0 else "",
                "top_1_score": docs[0].score if len(docs) > 0 else "",
                "top_2_dest": docs[1].destination if len(docs) > 1 else "",
                "top_2_score": docs[1].score if len(docs) > 1 else "",
                "top_3_dest": docs[2].destination if len(docs) > 2 else "",
                "top_3_score": docs[2].score if len(docs) > 2 else "",
                "confidence": result.confidence,
                "relevant": "true" if hit else "false",
                "notes": "",
            })

        if bad_retrievals:
            print("=== Flagged retrievals ===")
            for item in bad_retrievals:
                print(item)
        else:
            print("=== All queries returned expected destinations ===")

        _write_results(csv_rows)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_tests())
