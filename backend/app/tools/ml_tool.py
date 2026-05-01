import asyncio
from typing import Literal

import structlog
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.services.ml_service import MLService

log = structlog.get_logger()

Climate = Literal["tropical", "subtropical", "temperate", "continental", "highland", "arid"]
BudgetTier = Literal["budget", "mid", "luxury"]


class ClassifyDestinationInput(BaseModel):
    destination: str = Field(..., min_length=1, max_length=100, description="Destination city name")
    climate: Climate = Field(..., description="Climate type of the destination")
    budget_tier: BudgetTier = Field(..., description="Cost level: budget, mid, or luxury")
    best_season: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Best travel months, e.g. 'Nov-Feb' or 'Apr-Oct,Dec-Mar'",
    )
    tags: str = Field(
        ...,
        min_length=1,
        description="Comma-separated destination keywords, e.g. 'temple,culture,heritage,colonial'",
    )


def make_ml_tool(ml_service: MLService) -> StructuredTool:
    """Return a LangChain StructuredTool that classifies a destination's travel style.

    Wraps MLService.predict() (synchronous joblib model) in asyncio.to_thread
    so it doesn't block the event loop. Captures ml_service via closure.
    """

    async def _execute(
        destination: str,
        climate: str,
        budget_tier: str,
        best_season: str,
        tags: str,
    ) -> str:
        try:
            features = {
                "climate": climate,
                "budget_tier": budget_tier,
                "best_season": best_season,
                "tags": tags,
            }
            label = await asyncio.to_thread(ml_service.predict, features)
            log.info("ml_tool_result", destination=destination, label=label)
            return (
                f"ML travel-style classification for {destination}: **{label}**\n"
                f"(features: climate={climate}, budget_tier={budget_tier}, "
                f"best_season={best_season}, tags={tags})"
            )
        except RuntimeError as exc:
            return f"ML model unavailable: {exc}"
        except Exception as exc:
            log.error("ml_tool_failed", destination=destination, error=str(exc))
            return f"Classification failed for {destination}: {exc}"

    return StructuredTool.from_function(
        name="classify_destination",
        description=(
            "Classify a travel destination's style using a trained ML model. "
            "Returns one of: adventure, relaxation, culture, budget, luxury, family. "
            "Call this after rag_search to get an ML-predicted travel style for the top destination. "
            "Extract climate, budget_tier, best_season, and tags from the RAG search results."
        ),
        args_schema=ClassifyDestinationInput,
        coroutine=_execute,
    )
