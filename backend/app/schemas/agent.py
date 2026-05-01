from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentQuery(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)


class CostBreakdown(BaseModel):
    """Per-query cost: Groq (free) vs theoretical Gemini paid-tier equivalents."""

    # Per-step token counts
    cheap_model: str = ""
    cheap_calls: int = 0
    cheap_input_tokens: int = 0
    cheap_output_tokens: int = 0

    strong_model: str = ""
    strong_calls: int = 0
    strong_input_tokens: int = 0
    strong_output_tokens: int = 0

    total_input_tokens: int = 0
    total_output_tokens: int = 0

    # Actual cost on Groq free tier
    actual_cost_usd: float = 0.0

    # Theoretical cost on Gemini paid tier (April 2026 pricing, ≤200k context)
    # Flash-Lite: $0.125/1M in, $0.75/1M out
    # Flash:      $0.50/1M  in, $3.00/1M out
    # Pro:        $2.00/1M  in, $12.00/1M out
    gemini_flash_lite_usd: float = 0.0
    gemini_flash_usd: float = 0.0
    gemini_pro_usd: float = 0.0


class AgentResponse(BaseModel):
    run_id: str
    status: str
    response: str | None = None
    tool_trace: list[dict[str, Any]] | None = None
    cost_analysis: CostBreakdown | None = None


class AgentRunSummary(BaseModel):
    id: str
    query: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
