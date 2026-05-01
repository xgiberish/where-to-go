"""Agent endpoint tests.

Strategy: patch build_graph to return a fake compiled graph so no real
LLM, RAG, or ML calls happen. The fake graph returns a known message list
that extract_tool_trace() can parse — this exercises the full DB persistence
path (AgentRun + ToolCall) without external dependencies.
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy import select

from app.db.models import AgentRun, ToolCall


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_token(client: AsyncClient, email: str = "agent@example.com") -> str:
    await client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "password123"}
    )
    r = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": "password123"}
    )
    return r.json()["access_token"]


def _make_mock_graph(response_text: str = "Bali is perfect for beaches.") -> AsyncMock:
    """Return a mock compiled LangGraph graph with a predictable 3-tool trace."""
    ai_tool_call = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "rag_search",
                "args": {"query": "beach destination", "top_k": 5},
                "id": "call_rag_001",
                "type": "tool_call",
            }
        ],
    )
    tool_result = ToolMessage(
        content="Bali is a tropical beach destination in Indonesia.",
        tool_call_id="call_rag_001",
        name="rag_search",
    )
    synthesis = AIMessage(content=response_text)

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "messages": [
                HumanMessage(content="Best beach from Lebanon?"),
                AIMessage(content="User wants beach destination departing from Beirut."),
                ai_tool_call,
                tool_result,
                synthesis,
            ]
        }
    )
    return mock_graph


# ── Auth guard ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_query_agent_unauthenticated(client: AsyncClient):
    response = await client.post("/api/v1/agent/query", json={"query": "Best beach?"})
    assert response.status_code == 401


# ── Status and response ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_query_agent_returns_completed_status(client: AsyncClient):
    """Endpoint runs agent synchronously and returns completed, not pending."""
    token = await _get_token(client, "status@example.com")

    with patch("app.api.v1.agent.build_graph", return_value=_make_mock_graph()):
        response = await client.post(
            "/api/v1/agent/query",
            json={"query": "Best beach destination from Lebanon?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["response"] == "Bali is perfect for beaches."
    assert "run_id" in data


# ── Full pipeline: DB persistence ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_run_persisted_as_completed(client: AsyncClient, db_session):
    """AgentRun is created, completed, and response is stored in DB."""
    token = await _get_token(client, "pipeline1@example.com")
    response_text = "I recommend Bali for its beaches and culture."

    with patch("app.api.v1.agent.build_graph", return_value=_make_mock_graph(response_text)):
        resp = await client.post(
            "/api/v1/agent/query",
            json={"query": "Where should I travel for beaches?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    run_id = uuid.UUID(resp.json()["run_id"])

    # Query DB directly — not relying on response body alone
    result = await db_session.execute(select(AgentRun).where(AgentRun.id == run_id))
    run = result.scalar_one_or_none()

    assert run is not None
    assert run.status == "completed"
    assert run.response == response_text
    assert run.query == "Where should I travel for beaches?"
    assert run.completed_at is not None


@pytest.mark.asyncio
async def test_pipeline_tool_calls_logged(client: AsyncClient, db_session):
    """Every tool call in the trace is written to the tool_calls table."""
    token = await _get_token(client, "pipeline2@example.com")

    with patch("app.api.v1.agent.build_graph", return_value=_make_mock_graph()):
        resp = await client.post(
            "/api/v1/agent/query",
            json={"query": "Scuba diving destination from Beirut?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    run_id = uuid.UUID(resp.json()["run_id"])

    result = await db_session.execute(
        select(ToolCall).where(ToolCall.agent_run_id == run_id)
    )
    tool_calls = list(result.scalars())

    assert len(tool_calls) == 1
    tc = tool_calls[0]
    assert tc.tool_name == "rag_search"
    assert tc.tool_input == {"query": "beach destination", "top_k": 5}
    assert "Bali" in tc.tool_output
    assert tc.created_at is not None


@pytest.mark.asyncio
async def test_pipeline_tool_trace_in_response(client: AsyncClient):
    """tool_trace in the response contains call + result entries."""
    token = await _get_token(client, "pipeline3@example.com")

    with patch("app.api.v1.agent.build_graph", return_value=_make_mock_graph()):
        resp = await client.post(
            "/api/v1/agent/query",
            json={"query": "Beach trip from Beirut?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    trace = resp.json().get("tool_trace", [])
    calls = [t for t in trace if t["type"] == "call"]
    results = [t for t in trace if t["type"] == "result"]

    assert len(calls) == 1
    assert calls[0]["tool"] == "rag_search"
    assert len(results) == 1
    assert results[0]["tool"] == "rag_search"


# ── Failure path ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_failure_stored_in_db(client: AsyncClient, db_session):
    """When the graph raises, run is marked failed and error is stored."""
    token = await _get_token(client, "failure@example.com")

    failing_graph = AsyncMock()
    failing_graph.ainvoke = AsyncMock(side_effect=RuntimeError("Groq API down"))

    with patch("app.api.v1.agent.build_graph", return_value=failing_graph):
        resp = await client.post(
            "/api/v1/agent/query",
            json={"query": "Any destination from Beirut?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert "Groq API down" in data["response"]

    run_id = uuid.UUID(data["run_id"])
    result = await db_session.execute(select(AgentRun).where(AgentRun.id == run_id))
    run = result.scalar_one_or_none()

    assert run is not None
    assert run.status == "failed"
    assert "Groq API down" in run.response


# ── Discord webhook integration ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_discord_webhook_fired_on_completed_run(client: AsyncClient):
    """send_agent_result_to_discord is called as a background task when run completes."""
    token = await _get_token(client, "discord_ok@example.com")

    with (
        patch("app.api.v1.agent.build_graph", return_value=_make_mock_graph()),
        patch(
            "app.api.v1.agent.send_agent_result_to_discord",
            new_callable=AsyncMock,
        ) as mock_discord,
    ):
        resp = await client.post(
            "/api/v1/agent/query",
            json={"query": "Beach destination from Lebanon?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    mock_discord.assert_called_once()
    query_arg, response_arg, status_arg = mock_discord.call_args.args[:3]
    assert query_arg == "Beach destination from Lebanon?"
    assert response_arg == "Bali is perfect for beaches."
    assert status_arg == "completed"


@pytest.mark.asyncio
async def test_discord_webhook_fired_on_failed_run(client: AsyncClient):
    """send_agent_result_to_discord is called with status='failed' when the graph raises."""
    token = await _get_token(client, "discord_fail@example.com")

    failing_graph = AsyncMock()
    failing_graph.ainvoke = AsyncMock(side_effect=RuntimeError("Groq API down"))

    with (
        patch("app.api.v1.agent.build_graph", return_value=failing_graph),
        patch(
            "app.api.v1.agent.send_agent_result_to_discord",
            new_callable=AsyncMock,
        ) as mock_discord,
    ):
        resp = await client.post(
            "/api/v1/agent/query",
            json={"query": "Any destination?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.json()["status"] == "failed"
    mock_discord.assert_called_once()
    _, _, status_arg = mock_discord.call_args.args[:3]
    assert status_arg == "failed"


@pytest.mark.asyncio
async def test_discord_webhook_skipped_when_url_missing(client: AsyncClient):
    """When DISCORD_WEBHOOK_URL is not set, send_webhook is never called."""
    token = await _get_token(client, "discord_skip@example.com")

    with (
        patch("app.api.v1.agent.build_graph", return_value=_make_mock_graph()),
        patch(
            "app.services.discord_service.send_webhook",
            new_callable=AsyncMock,
        ) as mock_send,
    ):
        resp = await client.post(
            "/api/v1/agent/query",
            json={"query": "Beach destination from Lebanon?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    # Route still succeeds and send_webhook is never touched (URL is None in test settings)
    assert resp.status_code == 200
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_discord_webhook_receives_tool_trace(client: AsyncClient):
    """The tool_trace list is forwarded to send_agent_result_to_discord on completion."""
    token = await _get_token(client, "discord_trace@example.com")

    with (
        patch("app.api.v1.agent.build_graph", return_value=_make_mock_graph()),
        patch(
            "app.api.v1.agent.send_agent_result_to_discord",
            new_callable=AsyncMock,
        ) as mock_discord,
    ):
        await client.post(
            "/api/v1/agent/query",
            json={"query": "Beach from Lebanon?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    tool_trace_arg = mock_discord.call_args.args[3]
    assert isinstance(tool_trace_arg, list)
    call_entries = [t for t in tool_trace_arg if t["type"] == "call"]
    assert len(call_entries) == 1
    assert call_entries[0]["tool"] == "rag_search"
