import structlog
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.services.rag_service import RAGService

log = structlog.get_logger()


class RAGSearchInput(BaseModel):
    query: str = Field(..., min_length=3, max_length=500, description="Travel destination search query")
    top_k: int = Field(default=5, ge=1, le=10, description="Number of passages to retrieve")


def make_rag_tool(rag_service: RAGService) -> StructuredTool:
    """Return a LangChain StructuredTool that searches the destination knowledge base.

    Captures rag_service via closure — no global state.
    """

    async def _execute(query: str, top_k: int = 5) -> str:
        try:
            result = await rag_service.retrieve(query, top_k=top_k)
            if not result.documents:
                return "No relevant destination information found for that query."
            lines = [
                f"Retrieved {len(result.documents)} passages "
                f"(confidence={result.confidence:.2f}, "
                f"destinations={result.sources})\n"
            ]
            for doc in result.documents:
                lines.append(
                    f"[{doc.destination}] score={doc.score:.3f}:\n{doc.content[:500]}"
                )
            log.info("rag_tool_done", docs=len(result.documents), sources=result.sources)
            return "\n\n".join(lines)
        except Exception as exc:
            log.error("rag_tool_failed", error=str(exc))
            return f"RAG search failed: {exc}"

    return StructuredTool.from_function(
        name="rag_search",
        description=(
            "Search the travel destination knowledge base. "
            "Returns relevant Wikivoyage passages about destinations. "
            "Use this first to find destinations matching the user's travel interests."
        ),
        args_schema=RAGSearchInput,
        coroutine=_execute,
    )
