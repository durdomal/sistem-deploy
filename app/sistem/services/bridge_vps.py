"""VPS Bridge — исполнение allow-listed команд по SSH.

Модель безопасности:
- Хост должен быть зарегистрирован в bridge_vps_hosts для юзера.
- Команда должна пройти хотя бы один regex из allow_cmds.
- Аудит всего в audit_log.
- Timeout по умолчанию 60 сек, override через параметр (max 300).
- Для тестов работает MOCK-режим (переменная SISTEM_VPS_MOCK=1) — возвращает stub.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sistem.models import BridgeVpsHost

log = logging.getLogger("sistem.bridge.vps")


@dataclass
class VpsResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class VpsBridgeError(Exception):
    pass


async def run(
    session: AsyncSession, user_id, host: str, cmd: str, timeout: int = 60,
) -> VpsResult:
    if timeout < 1 or timeout > 300:
        raise VpsBridgeError("timeout must be between 1 and 300 seconds")

    row = (await session.execute(
        select(BridgeVpsHost).where(
            BridgeVpsHost.user_id == user_id,
            BridgeVpsHost.host == host,
            BridgeVpsHost.enabled.is_(True),
        )
    )).scalar_one_or_none()
    if not row:
        raise VpsBridgeError(f"host {host!r} not registered or disabled")

    # allowlist check — cmd должен match хотя бы одному паттерну
    allowed = list(row.allow_cmds or [])
    if not allowed:
        raise VpsBridgeError(f"host {host!r} has no allow_cmds — refusing to run anything")
    if not any(re.search(p, cmd) for p in allowed):
        raise VpsBridgeError(
            f"command not in allowlist for host {host!r}. Add regex to bridge_vps_hosts.allow_cmds."
        )

    if os.getenv("SISTEM_VPS_MOCK") == "1":
        return VpsResult(ok=True, exit_code=0,
                         stdout=f"[MOCK] host={host} cmd={cmd}\n",
                         stderr="", duration_ms=1)

    # реальный запуск через asyncssh
    try:
        import asyncssh  # type: ignore
    except ImportError as e:
        raise VpsBridgeError(f"asyncssh not installed: {e}")

    import time
    t0 = time.monotonic()
    ssh_kwargs = {
        "host": row.host,
        "username": row.ssh_user,
        "known_hosts": None,  # для private VPS; в проде — путь к known_hosts
    }
    if row.ssh_key_ref:
        ssh_kwargs["client_keys"] = [row.ssh_key_ref]
    try:
        async with asyncssh.connect(**ssh_kwargs) as conn:  # type: ignore
            result = await asyncio.wait_for(conn.run(cmd, check=False), timeout=timeout)
    except asyncio.TimeoutError:
        raise VpsBridgeError(f"command timed out after {timeout}s")
    except Exception as e:  # noqa: BLE001
        raise VpsBridgeError(f"ssh failed: {e}") from e

    return VpsResult(
        ok=(result.exit_status == 0),
        exit_code=result.exit_status or 0,
        stdout=str(result.stdout or ""),
        stderr=str(result.stderr or ""),
        duration_ms=int((time.monotonic() - t0) * 1000),
    )
