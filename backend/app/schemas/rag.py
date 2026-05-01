from pydantic import BaseModel, Field


class RAGDocument(BaseModel):
    content: str
    source: str
    destination: str
    score: float


class RAGResult(BaseModel):
    documents: list[RAGDocument]
    sources: list[str]
    confidence: float
    error: str | None = None
