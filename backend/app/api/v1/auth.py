from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt

from app.core.config import Settings, get_settings
from app.db.repositories.user_repo import UserRepository
from app.dependencies import DB
from app.schemas.auth import LoginResponse, SignupRequest, UserResponse

router = APIRouter()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_access_token(subject: str, settings: Settings) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": subject, "exp": expire},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupRequest,
    db: DB,
    settings: Annotated[Settings, Depends(get_settings)],
):
    repo = UserRepository(db)
    if await repo.get_by_email(body.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = await repo.create(body.email, _hash_password(body.password))
    return UserResponse(id=str(user.id), email=user.email, is_active=user.is_active)


@router.post("/login", response_model=LoginResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DB,
    settings: Annotated[Settings, Depends(get_settings)],
):
    repo = UserRepository(db)
    user = await repo.get_by_email(form.username)
    if not user or not _verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return LoginResponse(access_token=_create_access_token(str(user.id), settings))


@router.get("/me", response_model=UserResponse)
async def me(db: DB, settings: Annotated[Settings, Depends(get_settings)]):
    from app.dependencies import get_current_user
    raise HTTPException(status_code=501, detail="Use /me with Bearer token via dependency")
