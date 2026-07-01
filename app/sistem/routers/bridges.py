"""Bridge routes — VPS, n8n активны с Sprint 2; CC (Sprint 3), PC (v1.1) — заглушки."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from sistem.deps import CurrentUser, SessionDep
from sistem.models import AuditLog
from sistem.services.bridge_n8n import N8nBridgeError, trigger as n8n_trigger
from sistem.services.bridge_vps import VpsBridgeError, run as vps_run

log = logging.getLogger("sistem.bridges")
router = APIRouter()


class VpsRunBody(BaseModel):
    cmd: str
    timeout: int = 60


class VpsRunResponse(BaseModel):
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


@router.post("/vps/{host}/run", response_model=VpsRunResponse)
async def vps_run_endpoint(host: str, current: CurrentUser, session: SessionDep,
                            body: VpsRunBody = Body(...)):
    try:
        r = await vps_run(session, current.id, host, body.cmd, timeout=body.timeout)
    except VpsBridgeError as e:
        session.add(AuditLog(user_id=current.id, event="bridge.vps.rejected",
                             payload={"host": host, "cmd": body.cmd, "reason": str(e)}, ok=False))
        await session.commit()
        raise HTTPException(400, detail=str(e))

    session.add(AuditLog(user_id=current.id, event="bridge.vps.run",
                         payload={"host": host, "cmd": body.cmd, "exit_code": r.exit_code,
                                  "duration_ms": r.duration_ms}, ok=r.ok))
    await session.commit()
    return VpsRunResponse(ok=r.ok, exit_code=r.exit_code, stdout=r.stdout, stderr=r.stderr, duration_ms=r.duration_ms)


class N8nTriggerBody(BaseModel):
    payload: dict = {}
    timeout: int = 30


class N8nTriggerResponse(BaseModel):
    ok: bool
    status_code: int
    payload: dict | list | str | None
    duration_ms: int


@router.post("/n8n/trigger/{workflow}", response_model=N8nTriggerResponse)
async def n8n_trigger_endpoint(workflow: str, current: CurrentUser, session: SessionDep,
                                body: N8nTriggerBody = Body(...)):
    try:
        r = await n8n_trigger(session, current.id, workflow, payload=body.payload, timeout=body.timeout)
    except N8nBridgeError as e:
        session.add(AuditLog(user_id=current.id, event="bridge.n8n.rejected",
                             payload={"workflow": workflow, "reason": str(e)}, ok=False))
        await session.commit()
        raise HTTPException(400, detail=str(e))

    session.add(AuditLog(user_id=current.id, event="bridge.n8n.triggered",
                         payload={"workflow": workflow, "status": r.status_code, "duration_ms": r.duration_ms},
                         ok=r.ok))
    await session.commit()
    return N8nTriggerResponse(ok=r.ok, status_code=r.status_code, payload=r.payload, duration_ms=r.duration_ms)


# ─ CC bridge (Sprint 3) ─
class CcRunBody(BaseModel):
    prompt: str
    cwd: str = "default"
    timeout: int = 600
    allow_edits: bool = False


class CcRunResponse(BaseModel):
    ok: bool
    exit_code: int
    transcript: str
    stderr: str
    duration_ms: int
    files_changed: list[str]


@router.post("/cc/run", response_model=CcRunResponse)
async def cc_run_endpoint(current: CurrentUser, session: SessionDep, body: CcRunBody = Body(...)):
    from sistem.services.bridge_cc import run as cc_run, CcBridgeError
    try:
        r = await cc_run(prompt=body.prompt, cwd=body.cwd, timeout=body.timeout, allow_edits=body.allow_edits)
    except CcBridgeError as e:
        session.add(AuditLog(user_id=current.id, event="bridge.cc.rejected",
                             payload={"prompt_head": body.prompt[:100], "reason": str(e)}, ok=False))
        await session.commit()
        raise HTTPException(400, detail=str(e))
    session.add(AuditLog(user_id=current.id, event="bridge.cc.run",
                         payload={"prompt_head": body.prompt[:100], "exit_code": r.exit_code,
                                  "duration_ms": r.duration_ms, "files_changed": r.files_changed}, ok=r.ok))
    await session.commit()
    return CcRunResponse(ok=r.ok, exit_code=r.exit_code, transcript=r.transcript,
                         stderr=r.stderr, duration_ms=r.duration_ms, files_changed=r.files_changed)


@router.post("/pc/{pc_id}/run")
def pc_run(pc_id: str):
    raise HTTPException(501, detail="Local PC bridge deferred to v1.1")
