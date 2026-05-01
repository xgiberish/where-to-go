from fastapi import APIRouter

from app.db.repositories.agent_run_repo import AgentRunRepository
from app.dependencies import CurrentUser, DB
from app.schemas.agent import AgentRunSummary

router = APIRouter()


@router.get("/", response_model=list[AgentRunSummary])
async def get_history(current_user: CurrentUser, db: DB):
    repo = AgentRunRepository(db)
    runs = await repo.list_by_user(current_user.id)
    return [
        AgentRunSummary(
            id=str(r.id),
            query=r.query,
            status=r.status,
            created_at=r.created_at,
        )
        for r in runs
    ]
