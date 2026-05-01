from pydantic import BaseModel, computed_field


class LLMUsage(BaseModel):
    """Token usage and cost tracking for a single LLM call."""

    provider: str
    model: str
    tier: str           # "cheap" | "strong"
    call_type: str      # LLMCallType value
    input_tokens: int
    output_tokens: int
    actual_cost_usd: float
    is_free_tier: bool

    @computed_field
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @computed_field
    @property
    def cost_display(self) -> str:
        if self.is_free_tier:
            return f"${self.actual_cost_usd:.6f} (free tier, theoretical)"
        return f"${self.actual_cost_usd:.6f}"
