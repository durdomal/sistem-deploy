"""Executor — что реально делает воркер когда задача пришла.

MVP-логика:
- принимает task_id
- поднимает Task из БД
- логирует start
- вызывает handler:
    * `sistem:<name>` → нативные скиллы (kpi-report, competitor-watch, content-distribution)
    * `cowork:<plugin>:<skill>` → возвращает «инструкция для Cowork» (Sistem не запускает Cowork-скиллы напрямую;
       клиент/бот вызывает нужный скилл сам, а Sistem готовит контекст)
    * иначе — ошибка
- логирует finish
- пишет результат в Task.result
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from sistem.db import session_ctx
from sistem.models import AuditLog, Project, Skill, Task
from sistem.security import decrypt_pack_secrets, mask_pack_secrets

log = logging.getLogger("sistem.executor")


async def _run(task_id: UUID) -> dict:
    async with session_ctx() as session:
        task = (await session.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
        if not task:
            return {"ok": False, "error": "task not found"}
        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        await session.commit()

        skill_name = task.resolved_skill or ""
        skill = (await session.execute(select(Skill).where(Skill.name == skill_name))).scalar_one_or_none()
        if not skill or not skill.enabled:
            await _finish(session, task, ok=False, err=f"skill {skill_name!r} not registered/enabled")
            return {"ok": False, "error": f"skill {skill_name!r} unknown"}

        # соберём контекст проекта
        pack_context: dict | None = None
        if task.project_id:
            prj = (await session.execute(select(Project).where(Project.id == task.project_id))).scalar_one_or_none()
            if prj:
                # для нативных скиллов даём расшифрованный пак; для cowork — маскированный (Cowork сам возьмёт из своих коннекторов)
                pack_context = (
                    decrypt_pack_secrets(prj.pack)
                    if skill.handler.startswith("sistem:")
                    else mask_pack_secrets(prj.pack)
                )

        handler = skill.handler
        try:
            if handler.startswith("sistem:"):
                result = await _run_native(handler.split(":", 1)[1], task, pack_context)
            elif handler.startswith("cowork:"):
                # Sistem не запускает Cowork-скиллы напрямую — возвращает готовый invoke-стенограмму
                _, plugin, skill_slug = handler.split(":", 2)
                result = {
                    "type": "cowork_invoke",
                    "plugin": plugin,
                    "skill": skill_slug,
                    "params": task.resolved_params or {},
                    "project_context": pack_context,
                    "hint": f"Run `Skill {plugin}:{skill_slug}` in Cowork with the params above.",
                }
            elif handler.startswith("cc:"):
                # Sprint 3 — реальный вызов через CC bridge; пока — заглушка
                result = {"type": "cc_stub", "sprint": 3, "handler": handler}
            else:
                await _finish(session, task, ok=False, err=f"unknown handler prefix: {handler!r}")
                return {"ok": False, "error": "bad handler"}
        except Exception as e:  # noqa: BLE001
            log.exception("skill %s failed", skill_name)
            await _finish(session, task, ok=False, err=str(e))
            return {"ok": False, "error": str(e)}

        await _finish(session, task, ok=True, result=result)
        return {"ok": True, "result": result}


async def _finish(session, task: Task, *, ok: bool, result: dict | None = None, err: str | None = None) -> None:
    task.status = "done" if ok else "failed"
    task.result = result
    task.error = err
    task.finished_at = datetime.now(timezone.utc)
    session.add(AuditLog(user_id=task.user_id, project_id=task.project_id, task_id=task.id,
                         event=f"task.{task.status}", payload=result or ({"error": err} if err else None), ok=ok))
    await session.commit()


# ─── нативные скиллы ────────────────────────────────────────

async def _run_native(name: str, task: Task, pack_context: dict | None) -> dict:
    if name == "kpi-report":
        return _kpi_report(pack_context)
    if name == "content-distribution":
        return _content_distribution(task, pack_context)
    if name == "competitor-watch":
        return _competitor_watch(pack_context)
    return {"error": f"native skill {name!r} not implemented"}


def _kpi_report(pack_context: dict | None) -> dict:
    if not pack_context:
        return {"error": "kpi-report requires project_id"}
    goals = pack_context.get("goals") or {}
    kpis = goals.get("kpis") or []
    project = pack_context.get("project", {}).get("id", "?")
    palette = ((pack_context.get("brand_pack") or {}).get("palette") or ["#0A6AA1", "#666", "#eee"])
    accent = palette[0]
    rows = "".join(
        f'<tr><td>{k.get("name")}</td><td>{k.get("target")}</td><td>{k.get("current", "-")}</td><td>{k.get("window", "-")}</td></tr>'
        for k in kpis
    ) or '<tr><td colspan="4" style="opacity:.6">No KPIs in pack yet</td></tr>'
    html = (
        f'<div style="font:14px/1.5 system-ui,sans-serif;padding:16px;border-left:4px solid {accent};background:#fff;color:#111;max-width:640px">'
        f'<h3 style="margin:0 0 8px 0;color:{accent}">KPI · {project}</h3>'
        f'<p style="margin:0 0 12px 0;opacity:.75">Primary: <b>{goals.get("primary", "-")}</b></p>'
        f'<table style="width:100%;border-collapse:collapse;font-size:13px">'
        f'<thead><tr style="text-align:left;border-bottom:1px solid #ddd"><th>KPI</th><th>Target</th><th>Current</th><th>Window</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
        f'<p style="margin:12px 0 0 0;font-size:12px;opacity:.55">Sprint 5+: live-data via Meta/Google Ads MCP.</p>'
        f'</div>'
    )
    return {
        "type": "kpi-report",
        "project": project,
        "primary_goal": goals.get("primary"),
        "kpis": kpis,
        "html_artifact": html,
    }


def _content_distribution(task: Task, pack_context: dict | None) -> dict:
    if not pack_context:
        return {"error": "content-distribution requires project_id"}
    channels = pack_context.get("channels") or {}
    active = [k for k, v in channels.items() if isinstance(v, dict) and v]
    return {
        "type": "content-distribution",
        "project": pack_context.get("project", {}).get("id"),
        "text": (task.resolved_params or {}).get("text"),
        "channels_planned": active,
        "note": "Sprint 2 подключит Postiz как исполнителя; сейчас — план публикации.",
    }


def _competitor_watch(pack_context: dict | None) -> dict:
    if not pack_context:
        return {"error": "competitor-watch requires project_id"}
    comps = pack_context.get("competitors") or []
    return {
        "type": "competitor-watch",
        "project": pack_context.get("project", {}).get("id"),
        "competitors": [{"name": c.get("name"), "url": c.get("url")} for c in comps],
        "note": "Нужен Firecrawl или Apify ключ для реального обхода. Пока — только список из пака.",
    }


# ─── RQ entry ───────────────────────────────────────────────

def run_task(task_id_str: str) -> dict:
    """Entry point для RQ (синхронная обёртка над async)."""
    import asyncio
    return asyncio.run(_run(UUID(task_id_str)))
