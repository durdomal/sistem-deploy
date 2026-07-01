"""Skills registry — list + invoke."""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from sistem.deps import CurrentUser, SessionDep
from sistem.models import Project, Skill, Task
from sistem.services.queue import get_queue

router = APIRouter()


class SkillItem(BaseModel):
    name: str
    version: str
    description: Optional[str] = None
    handler: str
    enabled: bool


class InvokeBody(BaseModel):
    project_id: Optional[str] = None
    params: dict[str, Any] = {}


class InvokeResponse(BaseModel):
    task_id: UUID


@router.get("", response_model=list[SkillItem])
async def list_skills(session: SessionDep):
    rows = (await session.execute(
        select(Skill).where(Skill.enabled.is_(True)).order_by(Skill.name)
    )).scalars().all()
    return [
        SkillItem(name=s.name, version=s.version, description=s.description,
                  handler=s.handler, enabled=s.enabled)
        for s in rows
    ]


@router.post("/{name}/invoke", response_model=InvokeResponse)
async def invoke(name: str, current: CurrentUser, session: SessionDep,
                 body: InvokeBody = Body(...)):
    skill = (await session.execute(select(Skill).where(Skill.name == name))).scalar_one_or_none()
    if not skill or not skill.enabled:
        raise HTTPException(404, detail=f"skill {name!r} not found")

    prj_uuid = None
    if body.project_id:
        try:
            as_uuid = UUID(body.project_id)
            stmt = select(Project).where(Project.user_id == current.id, Project.id == as_uuid)
        except ValueError:
            stmt = select(Project).where(Project.user_id == current.id, Project.slug == body.project_id)
        prj = (await session.execute(stmt)).scalar_one_or_none()
        if not prj:
            raise HTTPException(404, detail=f"project {body.project_id!r} not found")
        prj_uuid = prj.id

    task = Task(user_id=current.id, project_id=prj_uuid, channel="api",
                input_text=f"skill.invoke:{name}", resolved_skill=name,
                resolved_params=body.params, status="queued")
    session.add(task); await session.commit(); await session.refresh(task)

    try:
        get_queue().enqueue("sistem.services.executor.run_task", str(task.id), job_timeout=300)
    except Exception:
        pass  # выполнится когда воркер поднимется

    return InvokeResponse(task_id=task.id)
