from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.lifespan import lifespan
from app.api.v1 import auth, agent, history

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(agent.router, prefix="/api/v1/agent", tags=["agent"])
app.include_router(history.router, prefix="/api/v1/history", tags=["history"])


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "app": settings.app_name}
