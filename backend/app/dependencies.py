from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db import models
from app.db.repositories.user_repo import UserRepository
from app.db.session import AsyncSessionLocal
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.ml_service import MLService
from app.services.rag_service import RAGService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


def get_embedding_service(request: Request) -> EmbeddingService:
    return request.app.state.embedding_service


def get_llm_service(request: Request) -> LLMService:
    return request.app.state.llm_service


def get_ml_service(request: Request) -> MLService:
    return request.app.state.ml_service


async def get_rag_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    embedding_service: Annotated[EmbeddingService, Depends(get_embedding_service)],
) -> RAGService:
    return RAGService(db, embedding_service)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> models.User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None or not user.is_active:
        raise credentials_exc
    return user


# Convenience type aliases for route signatures
DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[models.User, Depends(get_current_user)]
EmbeddingServiceDep = Annotated[EmbeddingService, Depends(get_embedding_service)]
LLMServiceDep = Annotated[LLMService, Depends(get_llm_service)]
MLServiceDep = Annotated[MLService, Depends(get_ml_service)]
RAGServiceDep = Annotated[RAGService, Depends(get_rag_service)]
