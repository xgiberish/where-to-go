"""Unit tests for the Discord notification service.

send_webhook is patched at the module level — no real HTTP requests are made.
Settings are supplied as MagicMock objects to avoid .env coupling.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.discord_service import build_discord_payload, send_agent_result_to_discord


# ── build_discord_payload ─────────────────────────────────────────────────────

class TestBuildDiscordPayload:

    def _build(self, **kwargs):
        defaults = dict(
            query="Best beach from Lebanon?",
            response="I recommend Bali.",
            status="completed",
            tool_trace=[
                {"type": "call", "tool": "rag_search"},
                {"type": "result", "tool": "rag_search"},
            ],
            timestamp="2024-01-01T00:00:00.000Z",
        )
        return build_discord_payload(**{**defaults, **kwargs})

    def test_top_level_has_embeds_key(self):
        assert "embeds" in self._build()

    def test_embed_has_required_discord_fields(self):
        embed = self._build()["embeds"][0]
        assert "title" in embed
        assert "color" in embed
        assert "fields" in embed
        assert "timestamp" in embed
        assert "footer" in embed

    def test_completed_run_uses_green_color(self):
        embed = self._build(status="completed")["embeds"][0]
        assert embed["color"] == 0x57F287

    def test_failed_run_uses_red_color(self):
        embed = self._build(status="failed")["embeds"][0]
        assert embed["color"] == 0xED4245

    def test_status_appears_in_title(self):
        title = self._build(status="completed")["embeds"][0]["title"]
        assert "COMPLETED" in title

    def test_question_field_present(self):
        fields = {f["name"]: f["value"] for f in self._build()["embeds"][0]["fields"]}
        assert fields["Question"] == "Best beach from Lebanon?"

    def test_answer_field_present(self):
        fields = {f["name"]: f["value"] for f in self._build()["embeds"][0]["fields"]}
        assert fields["Answer"] == "I recommend Bali."

    def test_tools_used_extracted_from_trace(self):
        trace = [
            {"type": "call", "tool": "rag_search"},
            {"type": "result", "tool": "rag_search"},
            {"type": "call", "tool": "classify_destination"},
            {"type": "result", "tool": "classify_destination"},
        ]
        fields = {f["name"]: f["value"] for f in self._build(tool_trace=trace)["embeds"][0]["fields"]}
        assert "rag_search" in fields["Tools Used"]
        assert "classify_destination" in fields["Tools Used"]

    def test_no_trace_shows_none(self):
        fields = {f["name"]: f["value"] for f in self._build(tool_trace=None)["embeds"][0]["fields"]}
        assert fields["Tools Used"] == "none"

    def test_empty_trace_shows_none(self):
        fields = {f["name"]: f["value"] for f in self._build(tool_trace=[])["embeds"][0]["fields"]}
        assert fields["Tools Used"] == "none"

    def test_only_call_entries_counted_not_results(self):
        # result entries must not add extra tool names
        trace = [
            {"type": "call", "tool": "rag_search"},
            {"type": "result", "tool": "rag_search"},
        ]
        fields = {f["name"]: f["value"] for f in self._build(tool_trace=trace)["embeds"][0]["fields"]}
        assert fields["Tools Used"] == "rag_search"

    def test_long_response_truncated_to_1024(self):
        long_response = "x" * 2000
        fields = {f["name"]: f["value"] for f in self._build(response=long_response)["embeds"][0]["fields"]}
        assert len(fields["Answer"]) <= 1024

    def test_long_query_truncated_to_1024(self):
        long_query = "q" * 2000
        fields = {f["name"]: f["value"] for f in self._build(query=long_query)["embeds"][0]["fields"]}
        assert len(fields["Question"]) <= 1024


# ── send_agent_result_to_discord ──────────────────────────────────────────────

def _fake_settings(discord_webhook_url=None):
    s = MagicMock()
    s.discord_webhook_url = discord_webhook_url
    return s


class TestSendAgentResultToDiscord:

    async def test_skips_when_url_is_none(self):
        with patch("app.services.discord_service.send_webhook", new_callable=AsyncMock) as mock_send:
            await send_agent_result_to_discord(
                "q", "r", "completed", None, _fake_settings(discord_webhook_url=None)
            )
        mock_send.assert_not_called()

    async def test_skips_when_url_is_empty_string(self):
        with patch("app.services.discord_service.send_webhook", new_callable=AsyncMock) as mock_send:
            await send_agent_result_to_discord(
                "q", "r", "completed", None, _fake_settings(discord_webhook_url="")
            )
        mock_send.assert_not_called()

    async def test_calls_send_webhook_with_correct_url(self):
        url = "https://discord.com/api/webhooks/123/abc"
        with patch(
            "app.services.discord_service.send_webhook",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_send:
            await send_agent_result_to_discord(
                "q", "r", "completed", [], _fake_settings(discord_webhook_url=url)
            )
        mock_send.assert_called_once()
        called_url = mock_send.call_args.args[0]
        assert called_url == url

    async def test_payload_passed_to_send_webhook_has_embeds(self):
        url = "https://discord.com/api/webhooks/123/abc"
        with patch(
            "app.services.discord_service.send_webhook",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_send:
            await send_agent_result_to_discord(
                "beach trip", "Go to Bali!", "completed", [], _fake_settings(discord_webhook_url=url)
            )
        payload = mock_send.call_args.args[1]
        assert "embeds" in payload
        fields = {f["name"]: f["value"] for f in payload["embeds"][0]["fields"]}
        assert fields["Question"] == "beach trip"
        assert fields["Answer"] == "Go to Bali!"

    async def test_does_not_raise_when_send_webhook_returns_false(self):
        with patch(
            "app.services.discord_service.send_webhook",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await send_agent_result_to_discord(
                "q", "r", "completed", None,
                _fake_settings(discord_webhook_url="https://discord.com/api/webhooks/x"),
            )
        assert result is None

    async def test_does_not_raise_on_unexpected_send_webhook_error(self):
        with patch(
            "app.services.discord_service.send_webhook",
            new_callable=AsyncMock,
            side_effect=RuntimeError("network exploded"),
        ):
            # Must NOT raise
            await send_agent_result_to_discord(
                "q", "r", "completed", None,
                _fake_settings(discord_webhook_url="https://discord.com/api/webhooks/x"),
            )

    async def test_failed_run_payload_has_correct_status(self):
        url = "https://discord.com/api/webhooks/123/abc"
        with patch(
            "app.services.discord_service.send_webhook",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_send:
            await send_agent_result_to_discord(
                "q", "Groq API down", "failed", None, _fake_settings(discord_webhook_url=url)
            )
        payload = mock_send.call_args.args[1]
        embed = payload["embeds"][0]
        assert embed["color"] == 0xED4245
        assert "FAILED" in embed["title"]
