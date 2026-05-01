from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentQuery(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)


class CostBreakdown(BaseModel):
    """Per-query cost analysis comparing Groq (free) vs paid providers."""

    cheap_tier: dict = {
        "calls": 0,
        "tokens": 0,
        "actual_cost": 0.0,
    }
    strong_tier: dict = {
        "calls": 0,
        "tokens": 0,
        "actual_cost": 0.0,
    }
    total: dict = {
        "tokens": 0,
        "actual_cost": 0.0,
        "vs_claude_haiku": 0.0,
        "vs_gemini_flash": 0.0,
        "savings_vs_claude": 0.0,
        "savings_vs_gemini": 0.0,
    }


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
