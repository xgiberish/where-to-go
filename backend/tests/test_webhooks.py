"""Tests for the user-triggered Discord webhook endpoint.

POST /api/v1/webhooks/discord/send-plan is auth-gated and manually fired
by the user from the frontend — never called automatically by the agent.

discord_webhook_url is patched directly on the lru_cache singleton so that
JWT auth (which also reads settings) continues to work unchanged.
"""
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.config import get_settings


async def _get_token(client: AsyncClient, email: str) -> str:
    await client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "password123"}
    )
    r = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": "password123"}
    )
    return r.json()["access_token"]


@contextmanager
def _discord_url(url: str | None):
    """Temporarily patch discord_webhook_url on the cached settings singleton."""
    settings = get_settings()
    original = settings.discord_webhook_url
    object.__setattr__(settings, "discord_webhook_url", url)
    try:
        yield
    finally:
        object.__setattr__(settings, "discord_webhook_url", original)


_PLAN_BODY = {
    "query": "Best beach from Lebanon?",
    "response": "I recommend Bali.",
    "status": "completed",
    "tool_trace": [
        {"type": "call", "tool": "rag_search", "input": {"query": "beach"}},
        {"type": "result", "tool": "rag_search", "output": "Bali is tropical."},
    ],
}


# ── Auth guard ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_plan_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v1/webhooks/discord/send-plan", json=_PLAN_BODY)
    assert resp.status_code == 401


# ── No webhook URL configured ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_plan_returns_failure_when_url_not_configured(client: AsyncClient):
    """Endpoint returns success=False when discord_webhook_url is None."""
    token = await _get_token(client, "wh_nourl@example.com")
    with _discord_url(None):
        resp = await client.post(
            "/api/v1/webhooks/discord/send-plan",
            json=_PLAN_BODY,
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "not configured" in data["message"].lower()


# ── Successful delivery ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_plan_returns_success_when_webhook_delivers(client: AsyncClient):
    token = await _get_token(client, "wh_ok@example.com")
    url = "https://discord.com/api/webhooks/test/abc"

    with (
        _discord_url(url),
        patch(
            "app.api.v1.webhooks.send_webhook",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_send,
    ):
        resp = await client.post(
            "/api/v1/webhooks/discord/send-plan",
            json=_PLAN_BODY,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "sent" in data["message"].lower()
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_plan_passes_correct_url_to_send_webhook(client: AsyncClient):
    token = await _get_token(client, "wh_url@example.com")
    webhook_url = "https://discord.com/api/webhooks/999/xyz"

    with (
        _discord_url(webhook_url),
        patch(
            "app.api.v1.webhooks.send_webhook",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_send,
    ):
        await client.post(
            "/api/v1/webhooks/discord/send-plan",
            json=_PLAN_BODY,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert mock_send.call_args.args[0] == webhook_url


# ── Failed delivery ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_plan_returns_failure_when_webhook_fails(client: AsyncClient):
    token = await _get_token(client, "wh_fail@example.com")

    with (
        _discord_url("https://discord.com/api/webhooks/test"),
        patch(
            "app.api.v1.webhooks.send_webhook",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        resp = await client.post(
            "/api/v1/webhooks/discord/send-plan",
            json=_PLAN_BODY,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "failed" in data["message"].lower()


@pytest.mark.asyncio
async def test_send_plan_does_not_raise_on_send_webhook_exception(client: AsyncClient):
    """Unexpected errors from send_webhook are caught; endpoint returns success=False."""
    token = await _get_token(client, "wh_exc@example.com")

    with (
        _discord_url("https://discord.com/api/webhooks/test"),
        patch(
            "app.api.v1.webhooks.send_webhook",
            new_callable=AsyncMock,
            side_effect=RuntimeError("network exploded"),
        ),
    ):
        resp = await client.post(
            "/api/v1/webhooks/discord/send-plan",
            json=_PLAN_BODY,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert resp.json()["success"] is False


# ── Payload shape ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_plan_payload_has_embeds(client: AsyncClient):
    """The payload forwarded to send_webhook contains a Discord embed."""
    token = await _get_token(client, "wh_payload@example.com")

    with (
        _discord_url("https://discord.com/api/webhooks/test"),
        patch(
            "app.api.v1.webhooks.send_webhook",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_send,
    ):
        await client.post(
            "/api/v1/webhooks/discord/send-plan",
            json=_PLAN_BODY,
            headers={"Authorization": f"Bearer {token}"},
        )

    payload = mock_send.call_args.args[1]
    assert "embeds" in payload
    fields = {f["name"]: f["value"] for f in payload["embeds"][0]["fields"]}
    assert fields["Question"] == "Best beach from Lebanon?"
    assert fields["Answer"] == "I recommend Bali."
