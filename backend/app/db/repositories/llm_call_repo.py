"""Repository for LLM call tracking."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LLMCall, LLMCallType, LLMTier
from app.services.llm_service import LLMResponse


class LLMCallRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_from_response(
        self,
        agent_run_id: uuid.UUID,
        response: LLMResponse,
    ) -> LLMCall:
        """Persist a single LLM call record from an LLMResponse."""
        call_type = response.call_type
        if call_type not in {m.value for m in LLMCallType}:
            call_type = LLMCallType.OTHER.value

        tier = response.tier
        if tier not in {m.value for m in LLMTier}:
            tier = LLMTier.CHEAP.value

        llm_call = LLMCall(
            agent_run_id=agent_run_id,
            call_type=call_type,
            tier=tier,
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            actual_cost_usd=response.actual_cost_usd,
            # Legacy DB columns — kept to avoid a migration; always 0 now that
            # Claude hypothetical costs have been removed from the cost model.
            hypothetical_claude_haiku_cost=0.0,
            hypothetical_claude_sonnet_cost=0.0,
            hypothetical_gemini_flash_cost=0.0,
            duration_ms=response.duration_ms or None,
        )
        self.db.add(llm_call)
        await self.db.flush()
        return llm_call

    async def get_by_agent_run(self, agent_run_id: uuid.UUID) -> list[LLMCall]:
        """All LLM calls for a given agent run, ordered by creation time."""
        result = await self.db.execute(
            select(LLMCall)
            .where(LLMCall.agent_run_id == agent_run_id)
            .order_by(LLMCall.created_at)
        )
        return list(result.scalars().all())
