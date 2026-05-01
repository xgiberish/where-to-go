import structlog
from fastapi import APIRouter, BackgroundTasks, Depends
from langchain_core.messages import HumanMessage
from typing import Annotated

from app.agents.graph import build_graph, extract_tool_trace
from app.core.config import Settings, get_settings
from app.db.repositories.agent_run_repo import AgentRunRepository
from app.db.repositories.tool_call_repo import ToolCallRepository
from app.dependencies import CurrentUser, DB, MLServiceDep, RAGServiceDep
from app.schemas.agent import AgentQuery, AgentResponse
from app.services.discord_service import send_agent_result_to_discord

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
    background_tasks: BackgroundTasks,
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

        log.info(
            "agent_run_completed",
            run_id=str(run.id),
            tools_called=[t["tool"] for t in tool_trace if t["type"] == "call"],
        )

        await run_repo.complete(run.id, final_message, tool_trace=tool_trace)

        tool_call_repo = ToolCallRepository(db)
        await tool_call_repo.log_from_trace(run.id, tool_trace)

        background_tasks.add_task(
            send_agent_result_to_discord,
            body.query, final_message, "completed", tool_trace, settings,
        )

        return AgentResponse(
            run_id=str(run.id),
            status="completed",
            response=final_message,
            tool_trace=tool_trace,
        )

    except Exception as exc:
        log.error("agent_run_failed", run_id=str(run.id), error=str(exc))
        await run_repo.fail(run.id, str(exc))

        background_tasks.add_task(
            send_agent_result_to_discord,
            body.query, str(exc), "failed", None, settings,
        )

        return AgentResponse(run_id=str(run.id), status="failed", response=str(exc))
