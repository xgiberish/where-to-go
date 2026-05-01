"""User-triggered webhook delivery endpoints."""
from datetime import datetime, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.dependencies import CurrentUser
from app.services.discord_service import build_discord_payload
from app.services.webhook_service import send_webhook

log = structlog.get_logger()
router = APIRouter()


class DiscordSendRequest(BaseModel):
    query: str
    response: str
    status: str = "completed"
    tool_trace: list[dict[str, Any]] | None = None


class DiscordSendResponse(BaseModel):
    success: bool
    message: str


@router.post("/discord/send-plan", response_model=DiscordSendResponse)
async def send_plan_to_discord(
    body: DiscordSendRequest,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DiscordSendResponse:
    """Send a completed trip plan to the configured Discord webhook.

    Called explicitly by the user via the frontend button — never automatic.
    Returns success/failure without raising so the frontend can show appropriate feedback.
    """
    if not settings.discord_webhook_url:
        return DiscordSendResponse(
            success=False,
            message="Discord webhook is not configured. Add DISCORD_WEBHOOK_URL to .env.",
        )

    try:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        payload = build_discord_payload(
            body.query, body.response, body.status, body.tool_trace, timestamp
        )
        ok = await send_webhook(settings.discord_webhook_url, payload)
        if ok:
            log.info("discord_plan_sent", user_id=str(current_user.id))
            return DiscordSendResponse(success=True, message="Plan sent to Discord.")
        return DiscordSendResponse(
            success=False,
            message="Failed to deliver to Discord. Check your webhook URL and try again.",
        )
    except Exception as exc:
        log.error("discord_send_error", error=str(exc), user_id=str(current_user.id))
        return DiscordSendResponse(success=False, message="An unexpected error occurred.")
