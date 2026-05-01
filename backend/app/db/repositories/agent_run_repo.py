import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRun


class AgentRunRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, user_id: uuid.UUID, query: str) -> AgentRun:
        run = AgentRun(user_id=user_id, query=query, status="pending")
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def list_by_user(self, user_id: uuid.UUID, limit: int = 20) -> list[AgentRun]:
        result = await self.db.execute(
            select(AgentRun)
            .where(AgentRun.user_id == user_id)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def complete(
        self,
        run_id: uuid.UUID,
        response: str,
        tool_trace: list[Any],
    ) -> AgentRun | None:
        run = await self.db.get(AgentRun, run_id)
        if run is None:
            return None
        run.response = response
        run.tool_trace = tool_trace
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def fail(self, run_id: uuid.UUID, error: str) -> AgentRun | None:
        run = await self.db.get(AgentRun, run_id)
        if run is None:
            return None
        run.status = "failed"
        run.response = error
        run.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(run)
        return run
