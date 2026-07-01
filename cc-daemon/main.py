"""claude-code-server — headless Claude Code daemon.

Запускается рядом с Sistem Core (docker-compose). Sistem вызывает через
POST /run с prompt + cwd, получает stdout транскрипт + список изменённых файлов + exit_code.

Использует официальный CLI `claude -p "<prompt>" --output-format json` (headless mode).
Требует: ANTHROPIC_API_KEY в окружении контейнера + установленный `claude` бинарник.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

log = logging.getLogger("cc-daemon")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="claude-code-server", version="1.0")

SHARED_SECRET = os.getenv("CC_DAEMON_SECRET", "")
WORKSPACE_ROOT = Path(os.getenv("CC_WORKSPACES", "/workspaces")).resolve()


class RunBody(BaseModel):
    prompt: str
    cwd: str = "default"                    # относительный путь в WORKSPACE_ROOT
    timeout: int = 600                      # секунды, max 30 мин
    allow_edits: bool = False               # если True — разрешаем writes (в v1: `--dangerously-skip-permissions`)
    env: dict[str, str] = {}


class RunResponse(BaseModel):
    ok: bool
    exit_code: int
    transcript: str
    stderr: str
    duration_ms: int
    cwd_abs: str
    files_changed: list[str] = []


def _check_auth(x_auth: str | None):
    if not SHARED_SECRET:
        raise HTTPException(500, "daemon misconfigured: no CC_DAEMON_SECRET")
    if not x_auth or not hmac.compare_digest(x_auth, SHARED_SECRET):
        raise HTTPException(401, "bad auth")


def _resolve_cwd(rel: str) -> Path:
    p = (WORKSPACE_ROOT / rel).resolve()
    if not str(p).startswith(str(WORKSPACE_ROOT)):
        raise HTTPException(400, "cwd escapes workspace root")
    p.mkdir(parents=True, exist_ok=True)
    return p


@app.get("/health")
def health():
    return {"ok": True, "workspaces": str(WORKSPACE_ROOT), "version": "1.0"}


@app.post("/run", response_model=RunResponse)
async def run_cc(body: RunBody, x_auth: str | None = Header(default=None, alias="X-Auth")):
    _check_auth(x_auth)
    if body.timeout < 1 or body.timeout > 1800:
        raise HTTPException(400, "timeout out of range")

    cwd = _resolve_cwd(body.cwd)

    # Снимок файлов до, чтобы посчитать изменения
    before = _snapshot(cwd)

    cmd = ["claude", "-p", body.prompt, "--output-format", "json"]
    if body.allow_edits:
        cmd.append("--dangerously-skip-permissions")

    env = os.environ.copy()
    env.update(body.env or {})

    t0 = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(cwd), env=env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=body.timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise HTTPException(408, f"CC timed out after {body.timeout}s")
    except FileNotFoundError:
        raise HTTPException(500, "`claude` binary not found in PATH")

    duration = int((time.monotonic() - t0) * 1000)
    after = _snapshot(cwd)
    files_changed = _diff(before, after)

    return RunResponse(
        ok=(proc.returncode == 0),
        exit_code=proc.returncode or 0,
        transcript=stdout.decode(errors="replace"),
        stderr=stderr.decode(errors="replace"),
        duration_ms=duration,
        cwd_abs=str(cwd),
        files_changed=files_changed,
    )


def _snapshot(root: Path) -> dict[str, str]:
    """SHA-1 всех файлов не глубже 5 уровней."""
    out = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root))
        if len(rel.split("/")) > 5 or p.stat().st_size > 5_000_000:
            continue
        try:
            out[rel] = hashlib.sha1(p.read_bytes()).hexdigest()
        except Exception:
            pass
    return out


def _diff(before: dict, after: dict) -> list[str]:
    added = [f for f in after if f not in before]
    removed = [f for f in before if f not in after]
    changed = [f for f in after if f in before and before[f] != after[f]]
    return sorted(added + changed + [f"-{f}" for f in removed])
