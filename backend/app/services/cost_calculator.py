"""Single source of truth for token/cost math.

Actual cost is reported as $0 for this project because Groq free-tier usage is
treated as free for the demo. Gemini values below are hypothetical comparison costs.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, BaseMessage

from app.schemas.agent import CostBreakdown

# ── Gemini API actual pricing (for real Gemini API calls via ENABLE_COST_DEMO) ──
# Gemini 1.5 Flash — the model used when ENABLE_COST_DEMO=true routes a call to Gemini
GEMINI_15_FLASH_INPUT_PRICE: float = 0.075  # per 1M input tokens
GEMINI_15_FLASH_OUTPUT_PRICE: float = 0.30  # per 1M output tokens

# ── Gemini hypothetical comparison prices (April 2026, ≤200k context window) ──
# Shown in the Cost Analysis panel as "what this run would cost on paid Gemini tiers"
_FLASH_LITE = (0.125, 0.75)   # (input_price, output_price) per 1M tokens
_FLASH      = (0.50,  3.00)
_PRO        = (2.00,  12.00)


def _gemini_cost(in_tok: int, out_tok: int, in_price: float, out_price: float) -> float:
    return round((in_tok * in_price + out_tok * out_price) / 1_000_000, 6)


def build_agent_cost_breakdown(
    messages: list[BaseMessage],
    settings: object,
) -> CostBreakdown:
    """Build CostBreakdown from a LangGraph agent message history.

    Reads per-call token usage from AIMessage.usage_metadata (populated by
    LangChain/ChatGroq). Attributes each call to cheap vs strong tier by matching
    the model name in response_metadata against settings.strong_model.

    Actual cost is always $0 — Groq free-tier is treated as free for this demo.
    Gemini costs are hypothetical comparisons only.
    """
    cheap_in = cheap_out = cheap_calls = 0
    strong_in = strong_out = strong_calls = 0

    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue
        usage = getattr(msg, "usage_metadata", None) or {}
        meta = getattr(msg, "response_metadata", None) or {}
        model_name = meta.get("model_name") or meta.get("model") or ""

        in_tok = usage.get("input_tokens", 0) or 0
        out_tok = usage.get("output_tokens", 0) or 0

        if settings.strong_model in model_name:
            strong_in += in_tok
            strong_out += out_tok
            strong_calls += 1
        else:
            cheap_in += in_tok
            cheap_out += out_tok
            cheap_calls += 1

    total_in = cheap_in + strong_in
    total_out = cheap_out + strong_out

    return CostBreakdown(
        cheap_model=settings.cheap_model,
        cheap_calls=cheap_calls,
        cheap_input_tokens=cheap_in,
        cheap_output_tokens=cheap_out,
        strong_model=settings.strong_model,
        strong_calls=strong_calls,
        strong_input_tokens=strong_in,
        strong_output_tokens=strong_out,
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        # Actual cost is $0 — Groq free-tier usage is treated as free for this demo.
        # Gemini values below are hypothetical comparison costs only.
        actual_cost_usd=0.0,
        gemini_flash_lite_usd=_gemini_cost(total_in, total_out, *_FLASH_LITE),
        gemini_flash_usd=_gemini_cost(total_in, total_out, *_FLASH),
        gemini_pro_usd=_gemini_cost(total_in, total_out, *_PRO),
    )
