"""Discord webhook notifications for agent run results.

Integrates with the existing send_webhook service (retry + timeout + logging).
Never raises — all failures are caught and logged so callers are fully isolated.
"""
from datetime import datetime, timezone

import structlog

from app.core.config import Settings
from app.services.webhook_service import send_webhook

log = structlog.get_logger()

# Discord sidebar colors
_STATUS_COLOR: dict[str, int] = {
    "completed": 0x57F287,  # green
    "failed": 0xED4245,     # red
}
_DEFAULT_COLOR = 0x5865F2   # Discord blurple


def build_discord_payload(
    query: str,
    response: str,
    status: str,
    tool_trace: list[dict] | None,
    timestamp: str,
) -> dict:
    """Return a Discord-compatible embed payload for an agent run result.

    Respects Discord's 1024-char field-value limit by truncating long strings.
    """
    tools_used = (
        ", ".join(
            sorted({t["tool"] for t in tool_trace if t.get("type") == "call"})
        )
        if tool_trace
        else "none"
    ) or "none"

    return {
        "embeds": [
            {
                "title": f"Agent Run — {status.upper()}",
                "color": _STATUS_COLOR.get(status, _DEFAULT_COLOR),
                "fields": [
                    {
                        "name": "Question",
                        "value": query[:1024],
                        "inline": False,
                    },
                    {
                        "name": "Status",
                        "value": status,
                        "inline": True,
                    },
                    {
                        "name": "Tools Used",
                        "value": tools_used,
                        "inline": True,
                    },
                    {
                        "name": "Answer",
                        "value": response[:1024],
                        "inline": False,
                    },
                ],
                "timestamp": timestamp,
                "footer": {"text": "Where To Go · AI Travel Planner"},
            }
        ]
    }


async def send_agent_result_to_discord(
    query: str,
    response: str,
    status: str,
    tool_trace: list[dict] | None,
    settings: Settings,
) -> None:
    """Fire an agent run result to the configured Discord webhook.

    Skips silently when DISCORD_WEBHOOK_URL is not set.
    Always returns None — never raises.
    """
    if not settings.discord_webhook_url:
        log.debug("discord_webhook_skipped", reason="DISCORD_WEBHOOK_URL not configured")
        return

    try:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        payload = build_discord_payload(query, response, status, tool_trace, timestamp)
        ok = await send_webhook(settings.discord_webhook_url, payload)
        if not ok:
            log.warning(
                "discord_webhook_not_delivered",
                status=status,
                query=query[:80],
            )
    except Exception as exc:
        log.error("discord_service_error", error=str(exc), query=query[:80])
