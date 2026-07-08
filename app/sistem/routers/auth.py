"""/auth/login и /auth/refresh."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from sistem.deps import SessionDep
from sistem.models import User
from sistem.security import create_access_token, create_refresh_token, decode_token, verify_password

router = APIRouter()


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshBody(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenPair)
async def login(body: LoginBody, session: SessionDep):
    email = body.email.lower()
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash) or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="bad creds")
    return TokenPair(
        access_token=create_access_token(sub=str(user.id), extra={"role": user.role}),
        refresh_token=create_refresh_token(sub=str(user.id)),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshBody, session: SessionDep):
    try:
        payload = decode_token(body.refresh_token)
    except ValueError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(e))
    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="wrong token type")
    sub = payload.get("sub")
    from uuid import UUID
    try:
        sub_uuid = UUID(sub)
    except (TypeError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="bad sub")
    user = (await session.execute(select(User).where(User.id == sub_uuid))).scalar_one_or_none()
    if not user or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="user gone")
    return TokenPair(
        access_token=create_access_token(sub=str(user.id), extra={"role": user.role}),
        refresh_token=create_refresh_token(sub=str(user.id)),
    )
