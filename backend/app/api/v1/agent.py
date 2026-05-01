import structlog
from fastapi import APIRouter, Depends
from langchain_core.messages import AIMessage, HumanMessage
from typing import Annotated

from app.agents.graph import build_graph, extract_tool_trace
from app.core.config import Settings, get_settings
from app.db.repositories.agent_run_repo import AgentRunRepository
from app.db.repositories.tool_call_repo import ToolCallRepository
from app.dependencies import CurrentUser, DB, MLServiceDep, RAGServiceDep
from app.schemas.agent import AgentQuery, AgentResponse, CostBreakdown

log = structlog.get_logger()
router = APIRouter()


@router.post("/query", response_model=AgentResponse)
async def query_agent(
    body: AgentQuery,
    current_user: CurrentUser,
    db: DB,
    rag_service: RAGServiceDep,
    ml_service: MLServiceDep,
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Run the LangGraph ReAct agent: rewrite → RAG → ML classify → live conditions → synthesize."""
    run_repo = AgentRunRepository(db)
    run = await run_repo.create(current_user.id, body.query)

    try:
        graph = build_graph(rag_service, ml_service, settings)

        result = await graph.ainvoke({
            "messages": [HumanMessage(content=body.query)]
        })

        final_message = result["messages"][-1].content
        tool_trace = extract_tool_trace(result["messages"])
        cost = _build_cost(result["messages"], settings)

        log.info(
            "agent_run_completed",
            run_id=str(run.id),
            tools_called=[t["tool"] for t in tool_trace if t["type"] == "call"],
            total_tokens=cost.total_input_tokens + cost.total_output_tokens,
        )

        await run_repo.complete(run.id, final_message, tool_trace=tool_trace)

        tool_call_repo = ToolCallRepository(db)
        await tool_call_repo.log_from_trace(run.id, tool_trace)

        return AgentResponse(
            run_id=str(run.id),
            status="completed",
            response=final_message,
            tool_trace=tool_trace,
            cost_analysis=cost,
        )

    except Exception as exc:
        log.error("agent_run_failed", run_id=str(run.id), error=str(exc))
        await run_repo.fail(run.id, str(exc))

        return AgentResponse(run_id=str(run.id), status="failed", response=str(exc))


def _build_cost(messages: list, settings: Settings) -> CostBreakdown:
    """Accumulate per-model token counts from AIMessage metadata and compute Gemini costs."""
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

    def _gemini(in_price: float, out_price: float) -> float:
        return round((total_in * in_price + total_out * out_price) / 1_000_000, 6)

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
        actual_cost_usd=0.0,
        gemini_flash_lite_usd=_gemini(0.125, 0.75),
        gemini_flash_usd=_gemini(0.50, 3.00),
        gemini_pro_usd=_gemini(2.00, 12.00),
    )
