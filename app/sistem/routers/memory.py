"""Memory API — universal / project / insights."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, or_, select

from sistem.deps import CurrentUser, SessionDep, require_self_or_admin
from sistem.models import MemoryInsight, MemoryProject, MemoryUniversal, Project

router = APIRouter()


class MemoryItem(BaseModel):
    id: UUID
    kind: str
    title: Optional[str] = None
    body: str
    tags: list[str] = []
    created_at: str


class MemoryCreate(BaseModel):
    kind: str
    title: Optional[str] = None
    body: str
    tags: list[str] = []


class InsightItem(MemoryItem):
    confidence: Optional[float] = None
    projects: list[UUID] = []


@router.get("/universal", response_model=list[MemoryItem])
async def universal(
    uid: UUID, current: CurrentUser, session: SessionDep,
    query: Optional[str] = Query(None), limit: int = Query(20, ge=1, le=200),
):
    require_self_or_admin(str(uid), current)
    stmt = select(MemoryUniversal).where(MemoryUniversal.user_id == uid)
    if query:
        q = f"%{query}%"
        stmt = stmt.where(or_(MemoryUniversal.title.ilike(q), MemoryUniversal.body.ilike(q)))
    stmt = stmt.order_by(desc(MemoryUniversal.created_at)).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        MemoryItem(id=r.id, kind=r.kind, title=r.title, body=r.body,
                   tags=list(r.tags or []), created_at=r.created_at.isoformat())
        for r in rows
    ]


@router.post("/universal", response_model=MemoryItem, status_code=201)
async def add_universal(uid: UUID, current: CurrentUser, session: SessionDep, item: MemoryCreate = Body(...)):
    require_self_or_admin(str(uid), current)
    row = MemoryUniversal(user_id=uid, kind=item.kind, title=item.title, body=item.body, tags=item.tags or [])
    session.add(row); await session.commit(); await session.refresh(row)
    return MemoryItem(id=row.id, kind=row.kind, title=row.title, body=row.body,
                     tags=list(row.tags or []), created_at=row.created_at.isoformat())


@router.get("/projects/{pid}", response_model=list[MemoryItem])
async def project_memory(
    uid: UUID, pid: str, current: CurrentUser, session: SessionDep,
    query: Optional[str] = Query(None), kind: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    require_self_or_admin(str(uid), current)
    prj = await _resolve_project(session, uid, pid)
    stmt = select(MemoryProject).where(
        MemoryProject.user_id == uid,
        MemoryProject.project_id == prj.id,
        MemoryProject.active.is_(True),
    )
    if kind:
        stmt = stmt.where(MemoryProject.kind == kind)
    if query:
        q = f"%{query}%"
        stmt = stmt.where(or_(MemoryProject.title.ilike(q), MemoryProject.body.ilike(q)))
    stmt = stmt.order_by(desc(MemoryProject.created_at)).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        MemoryItem(id=r.id, kind=r.kind, title=r.title, body=r.body,
                   tags=list(r.tags or []), created_at=r.created_at.isoformat())
        for r in rows
    ]


@router.post("/projects/{pid}", response_model=MemoryItem, status_code=201)
async def add_project_memory(
    uid: UUID, pid: str, current: CurrentUser, session: SessionDep,
    item: MemoryCreate = Body(...), source: Optional[str] = Query(None),
):
    require_self_or_admin(str(uid), current)
    prj = await _resolve_project(session, uid, pid)
    row = MemoryProject(
        user_id=uid, project_id=prj.id, kind=item.kind, title=item.title,
        body=item.body, tags=item.tags or [], source=source,
    )
    session.add(row); await session.commit(); await session.refresh(row)
    return MemoryItem(id=row.id, kind=row.kind, title=row.title, body=row.body,
                     tags=list(row.tags or []), created_at=row.created_at.isoformat())


@router.get("/insights", response_model=list[InsightItem])
async def insights(uid: UUID, current: CurrentUser, session: SessionDep,
                   limit: int = Query(20, ge=1, le=100)):
    require_self_or_admin(str(uid), current)
    stmt = select(MemoryInsight).where(MemoryInsight.user_id == uid).order_by(desc(MemoryInsight.created_at)).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        InsightItem(
            id=r.id, kind=r.kind, title=r.title, body=r.body, tags=[],
            created_at=r.created_at.isoformat(),
            confidence=float(r.confidence) if r.confidence is not None else None,
            projects=list(r.projects or []),
        )
        for r in rows
    ]


async def _resolve_project(session, uid: UUID, pid: str) -> Project:
    try:
        as_uuid = UUID(pid)
        stmt = select(Project).where(Project.user_id == uid, Project.id == as_uuid)
    except ValueError:
        stmt = select(Project).where(Project.user_id == uid, Project.slug == pid)
    prj = (await session.execute(stmt)).scalar_one_or_none()
    if not prj:
        raise HTTPException(404, detail=f"project {pid!r} not found")
    return prj
