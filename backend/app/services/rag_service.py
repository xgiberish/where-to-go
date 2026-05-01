import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.embedding_repo import EmbeddingRepository
from app.schemas.rag import RAGDocument, RAGResult
from app.services.embedding_service import EmbeddingService

log = structlog.get_logger()


class RAGService:
    def __init__(
        self,
        db: AsyncSession,
        embedding_service: EmbeddingService,
    ) -> None:
        self._repo = EmbeddingRepository(db)
        self._embedding = embedding_service

    # ── Chunking ──────────────────────────────────────────────────────────────

    def chunk_document(
        self,
        text: str,
        size: int = 512,
        overlap: int = 50,
    ) -> list[str]:
        """Split text into overlapping character-level chunks.

        Char-level matches ingest_rag_data.py and the RAG_CHUNK_SIZE/OVERLAP config
        values (512 chars / 50 chars). Consistent chunking ensures query-time
        retrieval operates in the same semantic space as the stored vectors.
        """
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + size
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(text):
                break
            start = end - overlap
        return chunks

    # ── Storage ───────────────────────────────────────────────────────────────

    async def store_document(
        self,
        dest_name: str,
        content: str,
        source: str = "manual",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ) -> int:
        """Chunk, embed, and upsert a destination document. Returns chunk count."""
        chunks = self.chunk_document(content, chunk_size, chunk_overlap)
        for idx, chunk in enumerate(chunks):
            embedding = await self._embedding.embed(chunk)
            await self._repo.upsert(
                document_id=dest_name,
                chunk_index=idx,
                content=chunk,
                embedding=embedding,
                destination=dest_name,
                metadata={"source": source, "destination": dest_name},
            )
        log.info("document_stored", dest=dest_name, chunks=len(chunks))
        return len(chunks)

    # ── Retrieval ─────────────────────────────────────────────────────────────

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> RAGResult:
        """Embed query, run cosine similarity search, return structured RAGResult."""
        query_embedding = await self._embedding.embed(query)
        results = await self._repo.similarity_search(query_embedding, top_k=top_k)

        documents = [
            RAGDocument(
                content=row.content,
                source=(row.metadata_ or {}).get("source", row.document_id),
                destination=row.destination or row.document_id,
                score=round(1.0 - distance, 4),
            )
            for row, distance in results
        ]

        # Unique destinations in ranked order
        seen: set[str] = set()
        sources: list[str] = []
        for doc in documents:
            if doc.destination not in seen:
                sources.append(doc.destination)
                seen.add(doc.destination)

        confidence = (
            round(sum(d.score for d in documents) / len(documents), 4)
            if documents else 0.0
        )

        log.info(
            "rag_retrieved",
            query=query[:80],
            docs=len(documents),
            confidence=confidence,
        )
        return RAGResult(documents=documents, sources=sources, confidence=confidence)
