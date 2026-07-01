"""Orchestrator-MCP endpoint.

Cowork Custom MCP умеет два транспорта:
- HTTP JSON-RPC 2.0 (POST /mcp)
- SSE (для стриминга; не используем в v1)

Аутентификация — Bearer JWT в заголовке. В настройках Custom MCP Тарас указывает URL
`https://sistem.globria.biz/mcp` + Bearer токен (long-lived API token, генерим в auth).

Тулы соответствуют §4 ARCHITECTURE (10 универсальных). Sprint 1 отгружает первые 5
(`sistem_command`, `sistem_status`, `sistem_project_context`, `sistem_query_memory`,
`sistem_log_event`), остальные 5 — заглушки, оживают в S2/S3/S4.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select

from sistem.db import get_session
from sistem.deps import SessionDep
from sistem.models import AuditLog, Project, Task, User
from sistem.security import decode_token, mask_pack_secrets
from sistem.services.queue import get_queue
from sistem.services.skill_resolver import resolve

log = logging.getLogger("sistem.mcp")
router = APIRouter()
_bearer = HTTPBearer(auto_error=True)


# ─── схемы тулов (MCP tools/list) ─────────────────────────

TOOLS = [
    {
        "name": "sistem_command",
        "description": "Главная точка входа: свободный текст → скилл + постановка в очередь. Возвращает task_id.",
        "inputSchema": {
            "type": "object",
            "required": ["text"],
            "properties": {
                "text": {"type": "string"},
                "project_id": {"type": "string"},
                "channel": {"type": "string", "default": "cowork"},
            },
        },
    },
    {
        "name": "sistem_status",
        "description": "Снимок системы: очередь, БД, версия, кол-во проектов.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "sistem_project_context",
        "description": "Отдать Project Pack (маскированный) для указанного проекта.",
        "inputSchema": {
            "type": "object",
            "required": ["project_id"],
            "properties": {"project_id": {"type": "string"}},
        },
    },
    {
        "name": "sistem_query_memory",
        "description": "Семантический поиск по памяти проекта. MVP — ILIKE по body/title.",
        "inputSchema": {
            "type": "object",
            "required": ["project_id", "query"],
            "properties": {
                "project_id": {"type": "string"},
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 10, "maximum": 100},
            },
        },
    },
    {
        "name": "sistem_log_event",
        "description": "Записать событие в audit_log (для интеграций/бриджей).",
        "inputSchema": {
            "type": "object",
            "required": ["event"],
            "properties": {
                "event": {"type": "string"},
                "project_id": {"type": "string"},
                "payload": {"type": "object"},
            },
        },
    },
    # ─ Sprint 2+ (заглушки) ─
    {
        "name": "sistem_run_on_vps",
        "description": "Выполнить allow-listed команду на зарегистрированном VPS-хосте. Доступно с Sprint 2.",
        "inputSchema": {
            "type": "object", "required": ["host", "cmd"],
            "properties": {"host": {"type": "string"}, "cmd": {"type": "string"}},
        },
    },
    {
        "name": "sistem_run_claude_code",
        "description": "Запустить headless Claude Code на VPS через bridge. Доступно с Sprint 3.",
        "inputSchema": {
            "type": "object", "required": ["prompt"],
            "properties": {"prompt": {"type": "string"}, "cwd": {"type": "string"}, "target_machine": {"type": "string", "default": "vps"}},
        },
    },
    {
        "name": "sistem_run_on_pc",
        "description": "Выполнить команду на локальном ПК через sistem-local-agent + Cloudflared. Доступно с Sprint 4.",
        "inputSchema": {
            "type": "object", "required": ["pc_id", "cmd"],
            "properties": {"pc_id": {"type": "string"}, "cmd": {"type": "string"}},
        },
    },
    {
        "name": "sistem_trigger_n8n",
        "description": "Триггернуть n8n workflow по webhook. Доступно с Sprint 2.",
        "inputSchema": {
            "type": "object", "required": ["workflow"],
            "properties": {"workflow": {"type": "string"}, "payload": {"type": "object"}},
        },
    },
    {
        "name": "sistem_skill_invoke",
        "description": "Прямой вызов скилла с параметрами (обход резолвера).",
        "inputSchema": {
            "type": "object", "required": ["skill"],
            "properties": {"skill": {"type": "string"}, "project_id": {"type": "string"}, "params": {"type": "object"}},
        },
    },
]


# ─── auth для MCP ────────────────────────────────────────────

async def _mcp_user(creds: HTTPAuthorizationCredentials = Depends(_bearer), session=Depends(get_session)) -> User:
    try:
        payload = decode_token(creds.credentials)
    except ValueError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(e))
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="need access token")
    user = (await session.execute(select(User).where(User.id == payload.get("sub")))).scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="user gone")
    return user


# ─── JSON-RPC 2.0 обёртка ────────────────────────────────────

class RpcReq(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str
    params: dict[str, Any] = {}


class RpcResp(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str | None = None
    result: Any = None
    error: dict[str, Any] | None = None


@router.post("", response_model=RpcResp)
async def mcp_endpoint(req: RpcReq = Body(...), user: User = Depends(_mcp_user), session: SessionDep = None):
    try:
        if req.method == "initialize":
            return RpcResp(id=req.id, result={
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "sistem", "version": "1.0.0"},
                "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
            })
        if req.method == "tools/list":
            return RpcResp(id=req.id, result={"tools": TOOLS})
        if req.method == "tools/call":
            name = req.params.get("name")
            args = req.params.get("arguments") or {}
            content = await _dispatch(name, args, user, session)
            return RpcResp(id=req.id, result={"content": content})
        return RpcResp(id=req.id, error={"code": -32601, "message": f"method {req.method!r} not found"})
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log.exception("MCP error")
        return RpcResp(id=req.id, error={"code": -32000, "message": str(e)})


async def _dispatch(name: str, args: dict[str, Any], user: User, session) -> list[dict]:
    if name == "sistem_status":
        prjs = (await session.execute(select(Project).where(Project.user_id == user.id))).scalars().all()
        info = {
            "version": "1.0.0",
            "user": user.email,
            "projects": [{"slug": p.slug, "name": p.name, "niche": p.niche, "status": p.status} for p in prjs],
            "count": len(prjs),
        }
        rows = "".join(
            f'<tr><td><b>{p.name}</b></td><td>{p.slug}</td><td>{p.niche}</td><td>{p.status}</td></tr>'
            for p in prjs
        ) or '<tr><td colspan="4" style="opacity:.6">No projects yet</td></tr>'
        html = (
            '<div style="font:14px/1.5 system-ui;padding:16px;border-left:4px solid #0A6AA1;background:#fff;color:#111;max-width:640px">'
            f'<h3 style="margin:0 0 8px 0">Sistem · {user.email}</h3>'
            f'<p style="margin:0 0 12px 0;opacity:.7">{len(prjs)} project(s) registered · v1.0.0</p>'
            '<table style="width:100%;border-collapse:collapse;font-size:13px">'
            '<thead><tr style="text-align:left;border-bottom:1px solid #ddd"><th>Name</th><th>Slug</th><th>Niche</th><th>Status</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>'
            '</div>'
        )
        info["html_artifact"] = html
        return _text(info)

    if name == "sistem_command":
        from sistem.routers.command import command, CommandBody
        body = CommandBody(
            text=args["text"],
            project_id=args.get("project_id"),
            channel=args.get("channel", "cowork"),
        )
        r = await command(body=body, current=user, session=session)
        return _text(r.model_dump(mode="json"))

    if name == "sistem_project_context":
        pid = args["project_id"]
        prj = await _lookup_project(session, user.id, pid)
        return _text({"project_id": str(prj.id), "slug": prj.slug, "pack": mask_pack_secrets(prj.pack)})

    if name == "sistem_query_memory":
        from sistem.routers.memory import project_memory
        rows = await project_memory(
            uid=user.id, pid=args["project_id"], current=user, session=session,
            query=args.get("query"), kind=None, limit=int(args.get("limit", 10)),
        )
        return _text([r.model_dump(mode="json") for r in rows])

    if name == "sistem_log_event":
        prj = None
        if args.get("project_id"):
            prj = await _lookup_project(session, user.id, args["project_id"])
        session.add(AuditLog(user_id=user.id, project_id=prj.id if prj else None,
                             event=args["event"], payload=args.get("payload"), ok=True))
        await session.commit()
        return _text({"logged": True, "event": args["event"]})

    if name == "sistem_skill_invoke":
        from sistem.routers.skills import invoke, InvokeBody
        r = await invoke(
            name=args["skill"], current=user, session=session,
            body=InvokeBody(project_id=args.get("project_id"), params=args.get("params") or {}),
        )
        return _text(r.model_dump(mode="json"))

    if name == "sistem_run_on_vps":
        from sistem.services.bridge_vps import run as vps_run, VpsBridgeError
        try:
            r = await vps_run(session, user.id, args["host"], args["cmd"], timeout=int(args.get("timeout", 60)))
            return _text({"ok": r.ok, "exit_code": r.exit_code, "stdout": r.stdout,
                          "stderr": r.stderr, "duration_ms": r.duration_ms})
        except VpsBridgeError as e:
            return _text({"ok": False, "error": str(e)})

    if name == "sistem_trigger_n8n":
        from sistem.services.bridge_n8n import trigger as n8n_trig, N8nBridgeError
        try:
            r = await n8n_trig(session, user.id, args["workflow"], payload=args.get("payload") or {},
                               timeout=int(args.get("timeout", 30)))
            return _text({"ok": r.ok, "status_code": r.status_code, "payload": r.payload,
                          "duration_ms": r.duration_ms})
        except N8nBridgeError as e:
            return _text({"ok": False, "error": str(e)})

    if name == "sistem_run_claude_code":
        from sistem.services.bridge_cc import run as cc_run, CcBridgeError
        try:
            r = await cc_run(
                prompt=args["prompt"], cwd=args.get("cwd", "default"),
                timeout=int(args.get("timeout", 600)),
                allow_edits=bool(args.get("allow_edits", False)),
            )
            return _text({"ok": r.ok, "exit_code": r.exit_code, "transcript": r.transcript[:8000],
                          "stderr": r.stderr[:2000], "duration_ms": r.duration_ms,
                          "files_changed": r.files_changed})
        except CcBridgeError as e:
            return _text({"ok": False, "error": str(e)})

    if name == "sistem_run_on_pc":
        return _text({"error": "tool deferred to v1.1 (Local PC bridge)", "status": "not_ready"})

    raise HTTPException(400, detail=f"unknown tool {name!r}")


def _text(obj) -> list[dict]:
    import json
    return [{"type": "text", "text": json.dumps(obj, ensure_ascii=False, default=str, indent=2)}]


async def _lookup_project(session, uid, pid: str) -> Project:
    from uuid import UUID
    try:
        as_uuid = UUID(pid)
        stmt = select(Project).where(Project.user_id == uid, Project.id == as_uuid)
    except ValueError:
        stmt = select(Project).where(Project.user_id == uid, Project.slug == pid)
    prj = (await session.execute(stmt)).scalar_one_or_none()
    if not prj:
        raise HTTPException(404, detail=f"project {pid!r} not found")
    return prj
