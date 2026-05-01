from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Embedding


class EmbeddingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upsert(
        self,
        document_id: str,
        chunk_index: int,
        content: str,
        embedding: list[float],
        destination: str = "",
        metadata: dict | None = None,
    ) -> Embedding:
        result = await self.db.execute(
            select(Embedding).where(
                Embedding.document_id == document_id,
                Embedding.chunk_index == chunk_index,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            row.content = content
            row.embedding = embedding
            row.destination = destination
            row.metadata_ = metadata
        else:
            row = Embedding(
                document_id=document_id,
                chunk_index=chunk_index,
                content=content,
                embedding=embedding,
                destination=destination,
                metadata_=metadata,
            )
            self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[tuple[Embedding, float]]:
        result = await self.db.execute(
            select(
                Embedding,
                Embedding.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .order_by("distance")
            .limit(top_k)
        )
        return [(row, float(dist)) for row, dist in result]
