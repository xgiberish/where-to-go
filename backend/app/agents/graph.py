"""LangGraph ReAct agent — two-model architecture.

Cheap model  (llama-3.1-8b-instant):     query rewrite + tool-call loop
Strong model (llama-3.3-70b-versatile):  final answer synthesis only

Graph:
  START → rewrite → agent ──(tool_calls?)──> tools → agent (loop)
                          └──(no tool_calls)──> synthesize → END
"""
import os
from typing import Annotated, TypedDict

import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.core.config import Settings
from app.services.ml_service import MLService
from app.services.rag_service import RAGService
from app.tools.ml_tool import make_ml_tool
from app.tools.rag_tool import make_rag_tool
from app.tools.weather_tool import make_live_conditions_tool

log = structlog.get_logger()

ALLOWED_TOOL_NAMES: frozenset[str] = frozenset({
    "rag_search",
    "classify_destination",
    "live_conditions",
})

# Cheap model: clarify what the user wants and where they're departing from
REWRITE_PROMPT = (
    "Rewrite the user's travel request as one clear sentence. "
    "Include: travel interest, any preferences (budget, climate, activities), "
    "and that departure is from Beirut, Lebanon. "
    "Output only the rewritten sentence — no recommendations."
)

# Cheap model: drive the tool-call loop — no synthesis
TOOL_AGENT_PROMPT = """You are a travel research assistant. Call these three tools in order:

1. rag_search — search the destination knowledge base
2. classify_destination — classify the top result's travel style via ML
3. live_conditions — get current weather and routes from Beirut (BEY)

Call all three tools. After the third tool call, output only: "Research complete.\""""

# Strong model: synthesize tool results into a coherent recommendation
SYNTHESIS_PROMPT = """You are a Smart Travel Planner. Using the tool results above, write ONE coherent recommendation.

Rules:
- State what the ML model classified the destination as AND what the knowledge base says.
  If they agree, confirm it. If they conflict, explain which source to trust more.
- Compare current weather against the destination's typical season.
  If there is a tension, flag it: "Note: currently X, which may affect Y."
- Include at least one route from Beirut with airline name and flight number.
- Name specific streets, temples, or activities. Vague answers are not acceptable.
- Write as one flowing narrative — not a list of tool outputs."""


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _log_usage(step: str, response: BaseMessage, **extra: object) -> None:
    """Emit a structured token-usage log line for every LLM call."""
    usage = getattr(response, "usage_metadata", None) or {}
    log.info(
        "token_usage",
        step=step,
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        total_tokens=usage.get("total_tokens"),
        **extra,
    )


def build_graph(
    rag_service: RAGService,
    ml_service: MLService,
    settings: Settings,
):
    """Build the two-model LangGraph agent. Called per-request (cheap — Python wiring only)."""
    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        log.info(
            "langsmith_tracing_enabled",
            project=settings.langsmith_project,
            endpoint=settings.langsmith_endpoint,
        )
    else:
        log.info("langsmith_tracing_disabled")

    tools = [
        make_rag_tool(rag_service),
        make_ml_tool(ml_service),
        make_live_conditions_tool(settings),
    ]

    registered = {t.name for t in tools}
    if registered != ALLOWED_TOOL_NAMES:
        raise RuntimeError(
            f"Tool allowlist violation: registered={registered}, expected={ALLOWED_TOOL_NAMES}"
        )

    # Cheap model: used for rewriting and tool-call decisions
    cheap_llm = ChatGroq(model=settings.cheap_model, api_key=settings.groq_api_key, temperature=0)
    # Strong model: used only for final synthesis — no tools bound
    strong_llm = ChatGroq(model=settings.strong_model, api_key=settings.groq_api_key, temperature=0)
    # Cheap model with tools bound — drives the ReAct loop
    cheap_llm_with_tools = cheap_llm.bind_tools(tools)

    # handle_tool_errors=True: catches ValidationError + exceptions, returns ToolMessage so LLM retries
    tool_node = ToolNode(tools, handle_tool_errors=True)

    # ── Node definitions ───────────────────────────────────────────────────────

    async def rewrite_node(state: AgentState) -> dict:
        """Cheap model: rewrite the user query into a clear travel intent sentence."""
        human_msg = next(m for m in state["messages"] if isinstance(m, HumanMessage))
        response = await cheap_llm.ainvoke([SystemMessage(content=REWRITE_PROMPT), human_msg])
        _log_usage("rewrite", response)
        return {"messages": [response]}

    async def agent_node(state: AgentState) -> dict:
        """Cheap model: decide which tools to call and extract their arguments."""
        response = await cheap_llm_with_tools.ainvoke(
            [SystemMessage(content=TOOL_AGENT_PROMPT)] + state["messages"]
        )
        _log_usage("agent", response, tool_calls=len(getattr(response, "tool_calls", []) or []))
        return {"messages": [response]}

    async def synthesize_node(state: AgentState) -> dict:
        """Strong model: synthesize all tool results into the final recommendation.

        Trims the cheap model's final no-tool message (its "Research complete." wrap-up)
        so the strong model works from clean tool results, not a premature summary.
        """
        messages = state["messages"]
        last_tool_idx = max(
            (i for i, m in enumerate(messages) if m.__class__.__name__ == "ToolMessage"),
            default=len(messages) - 1,
        )
        context = messages[: last_tool_idx + 1]
        response = await strong_llm.ainvoke([SystemMessage(content=SYNTHESIS_PROMPT)] + context)
        _log_usage("synthesize", response)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return "synthesize"

    # ── Graph wiring ──────────────────────────────────────────────────────────

    graph = StateGraph(AgentState)
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("synthesize", synthesize_node)

    graph.add_edge(START, "rewrite")
    graph.add_edge("rewrite", "agent")
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "synthesize": "synthesize"},
    )
    graph.add_edge("tools", "agent")
    graph.add_edge("synthesize", END)

    return graph.compile()


def extract_tool_trace(messages: list[BaseMessage]) -> list[dict]:
    """Build a structured tool-call trace from the agent message history."""
    trace: list[dict] = []
    for msg in messages:
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                trace.append({"type": "call", "tool": tc["name"], "input": tc["args"]})
        elif msg.__class__.__name__ == "ToolMessage":
            trace.append({
                "type": "result",
                "tool": getattr(msg, "name", "unknown"),
                "output": str(msg.content)[:600],
            })
    return trace
