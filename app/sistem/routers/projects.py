"""CRUD проектов + валидация Project Pack + шифрование секретов."""
from __future__ import annotations

from typing import Any
from uuid import UUID

import yaml
from fastapi import APIRouter, Body, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from sistem.deps import CurrentUser, SessionDep, require_self_or_admin
from sistem.models import Project
from sistem.security import decrypt_pack_secrets, encrypt_pack_secrets, mask_pack_secrets
from sistem.services.pack_validator import validate_pack

router = APIRouter()


class ProjectListItem(BaseModel):
    id: UUID
    slug: str
    name: str
    niche: str
    status: str


class ProjectDetail(ProjectListItem):
    pack: dict[str, Any]


@router.get("", response_model=list[ProjectListItem])
async def list_projects(uid: UUID, current: CurrentUser, session: SessionDep):
    require_self_or_admin(str(uid), current)
    rows = (await session.execute(select(Project).where(Project.user_id == uid))).scalars().all()
    return [ProjectListItem(id=p.id, slug=p.slug, name=p.name, niche=p.niche, status=p.status) for p in rows]


@router.post("", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
async def create_project(uid: UUID, current: CurrentUser, session: SessionDep, pack: dict[str, Any] = Body(...)):
    require_self_or_admin(str(uid), current)
    errs = validate_pack(pack)
    if errs:
        raise HTTPException(422, detail={"validation_errors": errs})
    p = pack["project"]
    slug = p["id"]
    existing = (await session.execute(
        select(Project).where(Project.user_id == uid, Project.slug == slug)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(409, detail=f"project {slug!r} already exists")
    stored = encrypt_pack_secrets(pack)
    prj = Project(user_id=uid, slug=slug, name=p["name"], niche=p["niche"], status=p["status"], pack=stored)
    session.add(prj); await session.commit(); await session.refresh(prj)
    return ProjectDetail(
        id=prj.id, slug=prj.slug, name=prj.name, niche=prj.niche, status=prj.status,
        pack=mask_pack_secrets(prj.pack),
    )


@router.post("/import", status_code=201)
async def import_yaml(uid: UUID, current: CurrentUser, session: SessionDep,
                     body: str = Body(..., media_type="text/yaml")):
    require_self_or_admin(str(uid), current)
    try:
        pack = yaml.safe_load(body)
    except yaml.YAMLError as e:
        raise HTTPException(400, detail=f"bad yaml: {e}")
    return await create_project(uid=uid, current=current, session=session, pack=pack)


@router.get("/{pid}", response_model=ProjectDetail)
async def get_project(uid: UUID, pid: str, current: CurrentUser, session: SessionDep,
                     format: str = Query("json"), include_secrets: bool = Query(False)):
    require_self_or_admin(str(uid), current)
    prj = await _lookup(session, uid, pid)
    pack = decrypt_pack_secrets(prj.pack) if include_secrets else mask_pack_secrets(prj.pack)
    return ProjectDetail(id=prj.id, slug=prj.slug, name=prj.name, niche=prj.niche, status=prj.status, pack=pack)


@router.put("/{pid}", response_model=ProjectDetail)
async def update_project(uid: UUID, pid: str, current: CurrentUser, session: SessionDep,
                        pack: dict[str, Any] = Body(...)):
    require_self_or_admin(str(uid), current)
    prj = await _lookup(session, uid, pid)
    errs = validate_pack(pack)
    if errs:
        raise HTTPException(422, detail={"validation_errors": errs})
    p = pack["project"]
    stored = encrypt_pack_secrets(pack)
    prj.name = p["name"]; prj.niche = p["niche"]; prj.status = p["status"]; prj.pack = stored
    await session.commit(); await session.refresh(prj)
    return ProjectDetail(
        id=prj.id, slug=prj.slug, name=prj.name, niche=prj.niche, status=prj.status,
        pack=mask_pack_secrets(prj.pack),
    )


@router.delete("/{pid}", status_code=204)
async def delete_project(uid: UUID, pid: str, current: CurrentUser, session: SessionDep):
    require_self_or_admin(str(uid), current)
    prj = await _lookup(session, uid, pid)
    await session.delete(prj); await session.commit()


async def _lookup(session, uid: UUID, pid: str) -> Project:
    try:
        as_uuid = UUID(pid)
        stmt = select(Project).where(Project.user_id == uid, Project.id == as_uuid)
    except ValueError:
        stmt = select(Project).where(Project.user_id == uid, Project.slug == pid)
    prj = (await session.execute(stmt)).scalar_one_or_none()
    if not prj:
        raise HTTPException(404, detail=f"project {pid!r} not found")
    return prj
