"""n8n Bridge — триггер workflow'ов по webhook.

Модель:
- Workflow должен быть зарегистрирован в bridge_n8n_workflows.
- webhook_url — production endpoint из n8n.
- Sistem кидает POST с payload → n8n возвращает результат (или accept + async).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sistem.models import BridgeN8nWorkflow

log = logging.getLogger("sistem.bridge.n8n")


@dataclass
class N8nResult:
    ok: bool
    status_code: int
    payload: Any
    duration_ms: int


class N8nBridgeError(Exception):
    pass


async def trigger(
    session: AsyncSession, user_id, workflow: str, payload: dict | None = None, timeout: int = 30,
) -> N8nResult:
    if timeout < 1 or timeout > 300:
        raise N8nBridgeError("timeout must be 1..300 seconds")

    # workflow — либо workflow_id, либо name
    stmt = (
        select(BridgeN8nWorkflow)
        .where(
            BridgeN8nWorkflow.user_id == user_id,
            BridgeN8nWorkflow.enabled.is_(True),
        )
        .where((BridgeN8nWorkflow.workflow_id == workflow) | (BridgeN8nWorkflow.name == workflow))
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        raise N8nBridgeError(f"workflow {workflow!r} not registered or disabled")

    if os.getenv("SISTEM_N8N_MOCK") == "1":
        return N8nResult(ok=True, status_code=200,
                         payload={"mock": True, "workflow": row.workflow_id, "payload": payload},
                         duration_ms=1)

    import time
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(row.webhook_url, json=payload or {})
    except httpx.RequestError as e:
        raise N8nBridgeError(f"n8n webhook unreachable: {e}") from e

    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}

    return N8nResult(
        ok=r.is_success,
        status_code=r.status_code,
        payload=data,
        duration_ms=int((time.monotonic() - t0) * 1000),
    )
