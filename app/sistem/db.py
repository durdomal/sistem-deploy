"""Async DB engine + session dependency."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sistem.config import get_settings

_engine = None
_SessionLocal: async_sessionmaker[AsyncSession] | None = None


def _init() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        return
    settings = get_settings()
    url = settings.database_url.replace("postgresql+psycopg://", "postgresql+asyncpg://")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    _engine = create_async_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=5, future=True)
    _SessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    _init()
    assert _SessionLocal is not None
    async with _SessionLocal() as session:
        yield session


@asynccontextmanager
async def session_ctx() -> AsyncIterator[AsyncSession]:
    _init()
    assert _SessionLocal is not None
    async with _SessionLocal() as session:
        yield session


async def ping() -> bool:
    _init()
    assert _engine is not None
    try:
        async with _engine.connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
        return True
    except Exception:
        return False
