"""FastAPI DI: current_user, session, admin-check."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sistem.db import get_session
from sistem.models import User
from sistem.security import decode_token

SessionDep = Annotated[AsyncSession, Depends(get_session)]
_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    session: SessionDep,
) -> User:
    try:
        payload = decode_token(creds.credentials)
    except ValueError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(e))
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="wrong token type")
    sub = payload.get("sub")
    try:
        uid = UUID(sub)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="bad sub")
    user = (await session.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if not user or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="user gone or suspended")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_self_or_admin(uid: str, current: User) -> None:
    if str(current.id) == uid or current.role in ("admin", "owner"):
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, detail="not your tenant")
