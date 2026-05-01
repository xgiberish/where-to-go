import time
from dataclasses import dataclass
from typing import Any, Literal

import structlog
from google import genai
from google.genai import types as genai_types
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import Settings
from app.services.cost_calculator import (
    GEMINI_15_FLASH_INPUT_PRICE,
    GEMINI_15_FLASH_OUTPUT_PRICE,
)

log = structlog.get_logger()


@dataclass
class LLMResponse:
    """LLM response with comprehensive cost tracking."""

    content: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    is_free_tier: bool

    # Routing metadata
    tier: str = "cheap"       # "cheap" | "strong"
    call_type: str = "other"  # LLMCallType value

    # Actual cost is $0 — Groq free-tier is treated as free for this demo
    actual_cost_usd: float = 0.0

    # Performance
    duration_ms: int = 0

    # Computed in __post_init__
    total_tokens: int = 0

    def __post_init__(self) -> None:
        self.total_tokens = self.input_tokens + self.output_tokens


class LLMService:
    """Three-tier LLM routing with cost tracking.

    Tier 1 (cheap)  → Groq llama-3.1-8b-instant      free, ~100ms, mechanical tasks
    Tier 2 (strong) → Groq llama-3.3-70b-versatile    free, ~300ms, complex synthesis
    Tier 3 (demo)   → Gemini gemini-1.5-flash          paid, cost-comparison only
                       enabled via settings.enable_cost_demo
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

        if settings.groq_api_key:
            self._groq = AsyncOpenAI(
                api_key=settings.groq_api_key,
                base_url=settings.groq_base_url,
            )
        if settings.gemini_api_key:
            self._gemini = genai.Client(api_key=settings.gemini_api_key)

    async def cheap_call(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 1024,
        use_demo: bool = False,
        call_type: str = "other",
    ) -> LLMResponse:
        """Fast tier for mechanical tasks (extraction, rewriting, classification)."""
        start = time.monotonic()
        if use_demo and self._settings.enable_cost_demo:
            response = await self._call_gemini(
                prompt, self._settings.demo_model, tier="cheap",
                system=system, max_tokens=max_tokens, call_type=call_type,
            )
        else:
            response = await self._call_groq(
                prompt, self._settings.cheap_model, tier="cheap",
                system=system, max_tokens=max_tokens, call_type=call_type,
            )
        response.duration_ms = int((time.monotonic() - start) * 1000)
        return response

    async def strong_call(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2048,
        use_demo: bool = False,
        call_type: str = "other",
    ) -> LLMResponse:
        """Smart tier for reasoning, synthesis, and final user-facing responses."""
        start = time.monotonic()
        if use_demo and self._settings.enable_cost_demo:
            response = await self._call_gemini(
                prompt, self._settings.demo_model, tier="strong",
                system=system, max_tokens=max_tokens, call_type=call_type,
            )
        else:
            response = await self._call_groq(
                prompt, self._settings.strong_model, tier="strong",
                system=system, max_tokens=max_tokens, call_type=call_type,
            )
        response.duration_ms = int((time.monotonic() - start) * 1000)
        return response

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def _call_groq(
        self,
        prompt: str,
        model: str,
        tier: Literal["cheap", "strong"],
        system: str | None = None,
        max_tokens: int = 1024,
        call_type: str = "other",
    ) -> LLMResponse:
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        api_response = await self._groq.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
        )

        input_tokens = api_response.usage.prompt_tokens if api_response.usage else 0
        output_tokens = api_response.usage.completion_tokens if api_response.usage else 0

        log.info(
            "llm_call_complete",
            provider="groq",
            model=model,
            tier=tier,
            call_type=call_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_cost_usd=0.0,
            is_free_tier=True,
        )

        return LLMResponse(
            content=api_response.choices[0].message.content or "",
            provider="groq",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            is_free_tier=True,
            tier=tier,
            call_type=call_type,
            actual_cost_usd=0.0,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def _call_gemini(
        self,
        prompt: str,
        model: str,
        tier: Literal["cheap", "strong"],
        system: str | None = None,
        max_tokens: int = 1024,
        call_type: str = "other",
    ) -> LLMResponse:
        cfg = genai_types.GenerateContentConfig(max_output_tokens=max_tokens)
        if system:
            cfg = genai_types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
            )

        api_response = await self._gemini.aio.models.generate_content(
            model=model,
            contents=prompt,
            config=cfg,
        )

        usage = api_response.usage_metadata
        input_tokens = usage.prompt_token_count if usage else 0
        output_tokens = usage.candidates_token_count if usage else 0

        actual_cost = (
            input_tokens / 1_000_000 * GEMINI_15_FLASH_INPUT_PRICE
            + output_tokens / 1_000_000 * GEMINI_15_FLASH_OUTPUT_PRICE
        )

        log.info(
            "llm_call_complete",
            provider="gemini",
            model=model,
            tier=tier,
            call_type=call_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_cost_usd=round(actual_cost, 8),
            is_free_tier=False,
        )

        return LLMResponse(
            content=api_response.text or "",
            provider="gemini",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            is_free_tier=False,
            tier=tier,
            call_type=call_type,
            actual_cost_usd=round(actual_cost, 8),
        )
