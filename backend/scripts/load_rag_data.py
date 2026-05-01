#!/usr/bin/env python3
"""
Where To Go — RAG data loader.

Reads destination documents from ml/data/raw/destinations/, embeds them via
OpenAI, and stores chunks in the pgvector embeddings table.

Expected layout:
    ml/data/raw/destinations/
        <destination_name>/
            overview.txt
            food.txt
            activities.txt
            ...

Run from backend/:
    python scripts/load_rag_data.py
    python scripts/load_rag_data.py --test-query "beach with warm weather"
    python scripts/load_rag_data.py --chunk-size 256 --chunk-overlap 32
    python scripts/load_rag_data.py --dest tokyo          # single destination
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Make `app` importable when run from backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import structlog

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import AsyncSessionLocal
from app.services.embedding_service import EmbeddingService
from app.services.rag_service import RAGService

log = structlog.get_logger()

REPO_ROOT = Path(__file__).resolve().parents[2]
DESTINATIONS_DIR = REPO_ROOT / "ml" / "data" / "raw" / "destinations"

OK = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
SKIP = "\033[33m–\033[0m"


# ── Loading ───────────────────────────────────────────────────────────────────

async def load_destination(
    rag: RAGService,
    dest_dir: Path,
    chunk_size: int,
    chunk_overlap: int,
) -> int:
    dest_name = dest_dir.name
    txt_files = sorted(dest_dir.glob("*.txt"))

    if not txt_files:
        print(f"  {SKIP} {dest_name}: no .txt files — skipped")
        return 0

    total = 0
    print(f"\n  Loading: \033[1m{dest_name}\033[0m  ({len(txt_files)} file(s))")
    for txt_file in txt_files:
        content = txt_file.read_text(encoding="utf-8").strip()
        if not content:
            print(f"    {SKIP} {txt_file.name}: empty — skipped")
            continue
        n = await rag.store_document(
            dest_name=dest_name,
            content=content,
            source=txt_file.name,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        total += n
        print(f"    {OK} {txt_file.name}: {n} chunk(s) stored")

    return total


async def load_all(
    rag: RAGService,
    only_dest: str | None,
    chunk_size: int,
    chunk_overlap: int,
) -> int:
    if not DESTINATIONS_DIR.exists():
        print(f"\n{FAIL} Destinations directory not found:")
        print(f"     {DESTINATIONS_DIR}")
        print(
            "\nCreate the directory and add destination folders:\n"
            "    ml/data/raw/destinations/<name>/*.txt"
        )
        return 0

    if only_dest:
        dest_dirs = [DESTINATIONS_DIR / only_dest]
        if not dest_dirs[0].is_dir():
            print(f"\n{FAIL} Destination not found: {only_dest}")
            return 0
    else:
        dest_dirs = sorted(d for d in DESTINATIONS_DIR.iterdir() if d.is_dir())

    if not dest_dirs:
        print(f"\n{FAIL} No destination folders in {DESTINATIONS_DIR}")
        return 0

    total_chunks = 0
    for dest_dir in dest_dirs:
        total_chunks += await load_destination(rag, dest_dir, chunk_size, chunk_overlap)

    return total_chunks


# ── Test retrieval ────────────────────────────────────────────────────────────

async def test_retrieval(rag: RAGService, query: str) -> None:
    print(f"\n── Test retrieval ─────────────────────────────────")
    print(f"   Query: \"{query}\"")
    results = await rag.retrieve(query, top_k=3)
    if not results:
        print(f"  {FAIL} No results returned.")
        return
    for i, r in enumerate(results, 1):
        snippet = r["content"][:100].replace("\n", " ")
        print(
            f"  {i}. [{r['document_id']}]  score={r['score']:.4f}\n"
            f"     {snippet}…"
        )


# ── Entry point ───────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Load destination docs into the RAG vector store")
    p.add_argument("--dest", default="", help="Load a single destination by folder name")
    p.add_argument("--test-query", default="", help="Run a retrieval test after loading")
    p.add_argument("--chunk-size", type=int, default=512, help="Words per chunk (default 512)")
    p.add_argument("--chunk-overlap", type=int, default=64, help="Word overlap (default 64)")
    p.add_argument("--no-test", action="store_true", help="Skip automatic test retrieval")
    return p.parse_args()


async def main() -> None:
    args = _parse_args()
    settings = get_settings()
    setup_logging(debug=settings.debug)

    print("\nWhere To Go — RAG Data Loader")
    print(f"  Destinations dir : {DESTINATIONS_DIR}")
    print(f"  Embedding model  : {settings.embedding_model}")
    print(f"  Chunk size       : {args.chunk_size} words  |  overlap: {args.chunk_overlap} words")


    async with AsyncSessionLocal() as db:
        rag = RAGService(
            db=db,
            embedding_service=EmbeddingService(settings),
        )

        total = await load_all(
            rag,
            only_dest=args.dest or None,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )

        print(f"\n── Summary ─────────────────────────────────────────")
        print(f"  Total chunks stored: {total}")

        if total > 0 and not args.no_test:
            query = args.test_query or "beach destination with warm weather and good food"
            await test_retrieval(rag, query)

    print("\nDone.\n")


if __name__ == "__main__":
    asyncio.run(main())
