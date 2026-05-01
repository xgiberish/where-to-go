"""
RAG ingestion script — Wikivoyage content -> pgvector embeddings.

Fetches Wikivoyage destination pages for 15 selected destinations,
splits content into chunks, generates Gemini text-embedding-004 vectors
(768 dims), and stores them in the `embeddings` table via EmbeddingRepository.

Chunking strategy
-----------------
Chunk size  : 512 characters (~80-100 words)
Overlap     : 50 characters (~8-10 words)

Justification:
  - 512 chars aligns with Wikivoyage's paragraph structure. Each chunk
    answers one coherent travel question (e.g. "what to do in Kyoto")
    without being so large that it dilutes retrieval precision.
  - 50-char overlap (~1 sentence fragment) preserves context at chunk
    boundaries so the model doesn't lose a sentence split across chunks.
  - Empirically, 300-600 char chunks outperform very short (~100 char)
    or very long (~2000 char) chunks for travel Q&A retrieval
    (RAG survey: Gao et al. 2023).

Usage:
    python backend/scripts/ingest_rag_data.py

    To test retrieval only (no ingest):
    python backend/scripts/ingest_rag_data.py --test-only
"""
import argparse
import asyncio
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_PROJECT_ROOT = _BACKEND_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))
sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models import Embedding
from app.db.repositories.embedding_repo import EmbeddingRepository
from data_processing.scrapers.wikivoyage_scraper import WikivoyageScraper

import structlog

log = structlog.get_logger()

# ── 15 destinations selected for RAG ──────────────────────────────────────────
# Chosen to cover all 6 travel styles with geographic variety
RAG_DESTINATIONS = [
    ("Bangkok", "Thailand"),
    ("Kyoto", "Japan"),
    ("Bali", "Indonesia"),          # Wikivoyage has a "Bali" article
    ("Hanoi", "Vietnam"),
    ("Siem Reap", "Cambodia"),
    ("Kathmandu", "Nepal"),
    ("Singapore", "Singapore"),
    ("Luang Prabang", "Laos"),
    ("Chiang Mai", "Thailand"),
    ("Tokyo", "Japan"),
    ("Pokhara", "Nepal"),
    ("Hoi An", "Vietnam"),
    ("Penang", "Malaysia"),
    ("Boracay", "Philippines"),
    ("Colombo", "Sri Lanka"),
]


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
    """Split text into overlapping character-level chunks.

    Character-level chunking is used (rather than word or sentence) to
    produce predictable, uniform chunk sizes regardless of word length.
    Overlap ensures sentence fragments at boundaries appear in both chunks.
    """
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


_EMBED_MODEL = None


def _get_embed_model():
    """Lazy-load sentence-transformers model (768 dims, matches Vector(768) schema)."""
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        from sentence_transformers import SentenceTransformer
        # all-mpnet-base-v2 produces 768-dim vectors, same dimension as
        # Gemini text-embedding-004 — no schema change needed
        _EMBED_MODEL = SentenceTransformer("all-mpnet-base-v2")
    return _EMBED_MODEL


async def embed_text(text: str, _settings=None) -> list[float]:
    """Generate a 768-dim embedding using sentence-transformers (local, no API key)."""
    model = _get_embed_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


async def ingest_destination(
    destination: str,
    country: str,
    paragraphs: list[str],
    repo: EmbeddingRepository,
    settings,
) -> int:
    """Chunk paragraphs, embed, and upsert to pgvector. Returns chunk count."""
    full_text = "\n\n".join(paragraphs)
    chunks = chunk_text(full_text, settings.rag_chunk_size, settings.rag_chunk_overlap)
    document_id = f"wikivoyage:{destination.lower().replace(' ', '_')}"

    ingested = 0
    for i, chunk in enumerate(chunks):
        try:
            embedding = await embed_text(chunk)
            await repo.upsert(
                document_id=document_id,
                chunk_index=i,
                content=chunk,
                embedding=embedding,
                destination=destination,
                metadata={
                    "destination": destination,
                    "country": country,
                    "source": "wikivoyage",
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            )
            ingested += 1
        except Exception as exc:
            log.warning("embed_failed", destination=destination, chunk=i, error=str(exc))

    log.info("ingested", destination=destination, chunks=ingested, total=len(chunks))
    return ingested


async def test_retrieval(repo: EmbeddingRepository, settings) -> None:
    """Run 5 hand-written queries and print top-3 retrieved chunks."""
    model = _get_embed_model()

    test_queries = [
        "best temples and ancient ruins to visit",
        "budget backpacking hostels cheap street food",
        "scuba diving and snorkelling spots",
        "luxury spa resort infinity pool",
        "trekking and hiking mountains",
    ]

    print("\n=== Retrieval test ===")
    for query in test_queries:
        query_vec = model.encode(query, normalize_embeddings=True).tolist()
        hits = await repo.similarity_search(query_vec, top_k=3)
        print(f"\nQuery: '{query}'")
        for emb, dist in hits:
            meta = emb.metadata_ or {}
            dest = meta.get("destination", emb.document_id)
            preview = emb.content[:120].replace("\n", " ")
            line = f"  [{dist:.3f}] {dest}: {preview}..."
            print(line.encode("ascii", errors="replace").decode("ascii"))


async def main(test_only: bool = False) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with WikivoyageScraper() as scraper:
        async with SessionLocal() as session:
            repo = EmbeddingRepository(session)

            if not test_only:
                total_chunks = 0
                for destination, country in RAG_DESTINATIONS:
                    paragraphs = await scraper.fetch_reviews(destination, country)
                    if not paragraphs:
                        log.warning("skipped_no_content", destination=destination)
                        continue
                    n = await ingest_destination(destination, country, paragraphs, repo, settings)
                    total_chunks += n

                print(f"\nIngested {len(RAG_DESTINATIONS)} destinations, {total_chunks} total chunks")

            await test_retrieval(repo, settings)

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-only", action="store_true", help="Skip ingest, only test retrieval")
    args = parser.parse_args()
    asyncio.run(main(test_only=args.test_only))
