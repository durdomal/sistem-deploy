"""POST /command — точка входа команд, GET /tasks/{id} — статус."""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from sistem.deps import CurrentUser, SessionDep
from sistem.models import AuditLog, Project, Task
from sistem.services.queue import get_queue
from sistem.services.skill_resolver import resolve

log = logging.getLogger("sistem.command")
router = APIRouter()


class CommandBody(BaseModel):
    text: str
    project_id: Optional[str] = None
    channel: str = "cowork"
    execute: bool = True


class CommandResponse(BaseModel):
    task_id: Optional[UUID] = None
    resolved_skill: str
    matched_rule: str
    project_id: Optional[str] = None
    confidence: float
    queued: bool


class TaskStatus(BaseModel):
    id: UUID
    status: str
    resolved_skill: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


@router.post("/command", response_model=CommandResponse)
async def command(body: CommandBody, current: CurrentUser, session: SessionDep):
    # авторезолв проекта через LLM/rule router — берём проекты юзера как контекст
    known = (await session.execute(
        select(Project.slug, Project.name, Project.niche).where(Project.user_id == current.id)
    )).all()
    known_projects = [{"slug": r[0], "name": r[1], "niche": r[2]} for r in known]
    resolution = resolve(body.text, explicit_project=body.project_id, known_projects=known_projects)

    prj_uuid = None
    if resolution.project_id:
        try:
            as_uuid = UUID(resolution.project_id)
            prj = (await session.execute(
                select(Project).where(Project.user_id == current.id, Project.id == as_uuid)
            )).scalar_one_or_none()
        except ValueError:
            prj = (await session.execute(
                select(Project).where(Project.user_id == current.id, Project.slug == resolution.project_id)
            )).scalar_one_or_none()
        if not prj and body.project_id:
            raise HTTPException(404, detail=f"project {resolution.project_id!r} not found")
        prj_uuid = prj.id if prj else None

    if not body.execute:
        return CommandResponse(
            task_id=None, resolved_skill=resolution.skill, matched_rule=resolution.matched_rule,
            project_id=resolution.project_id, confidence=resolution.confidence, queued=False,
        )

    task = Task(
        user_id=current.id, project_id=prj_uuid, channel=body.channel,
        input_text=body.text, resolved_skill=resolution.skill,
        resolved_params=resolution.params, status="queued",
    )
    session.add(task)
    session.add(AuditLog(
        user_id=current.id, project_id=prj_uuid, event="command.received",
        payload={"text": body.text, "skill": resolution.skill, "rule": resolution.matched_rule},
    ))
    await session.commit(); await session.refresh(task)

    try:
        get_queue().enqueue("sistem.services.executor.run_task", str(task.id), job_timeout=300)
    except Exception as e:
        log.warning("queue unavailable, task %s will run later: %s", task.id, e)

    return CommandResponse(
        task_id=task.id, resolved_skill=resolution.skill, matched_rule=resolution.matched_rule,
        project_id=resolution.project_id, confidence=resolution.confidence, queued=True,
    )


@router.get("/tasks/{task_id}", response_model=TaskStatus)
async def task_status(task_id: UUID, current: CurrentUser, session: SessionDep):
    t = (await session.execute(
        select(Task).where(Task.id == task_id, Task.user_id == current.id)
    )).scalar_one_or_none()
    if not t:
        raise HTTPException(404, detail="task not found")
    return TaskStatus(
        id=t.id, status=t.status, resolved_skill=t.resolved_skill, result=t.result, error=t.error,
        created_at=t.created_at.isoformat(),
        started_at=t.started_at.isoformat() if t.started_at else None,
        finished_at=t.finished_at.isoformat() if t.finished_at else None,
    )
