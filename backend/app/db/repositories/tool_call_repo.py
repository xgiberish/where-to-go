import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ToolCall


class ToolCallRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log_from_trace(
        self,
        agent_run_id: uuid.UUID,
        trace: list[dict[str, Any]],
    ) -> None:
        """Persist one ToolCall row per tool execution, pairing call with its result.

        The trace from extract_tool_trace() alternates:
          {"type": "call", "tool": name, "input": args}
          {"type": "result", "tool": name, "output": text}

        We create a row on "call" and fill tool_output when the matching "result" arrives.
        """
        pending: dict[str, ToolCall] = {}

        for entry in trace:
            if entry["type"] == "call":
                tc = ToolCall(
                    agent_run_id=agent_run_id,
                    tool_name=entry["tool"],
                    tool_input=entry.get("input"),
                )
                self.db.add(tc)
                pending[entry["tool"]] = tc

            elif entry["type"] == "result":
                tc = pending.get(entry["tool"])
                if tc is not None:
                    tc.tool_output = entry.get("output")

        await self.db.commit()
