"""Claude Code Bridge — вызов headless CC daemon.

daemon живёт на sistem-cc-daemon:8020 внутри compose-сети или на 127.0.0.1:8020 с хоста.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

log = logging.getLogger("sistem.bridge.cc")


@dataclass
class CcResult:
    ok: bool
    exit_code: int
    transcript: str
    stderr: str
    duration_ms: int
    files_changed: list[str]


class CcBridgeError(Exception):
    pass


async def run(
    prompt: str, cwd: str = "default", timeout: int = 600, allow_edits: bool = False,
    env: dict | None = None,
) -> CcResult:
    base = os.getenv("CC_DAEMON_URL", "http://cc-daemon:8020")
    secret = os.getenv("CC_DAEMON_SECRET", "")

    if os.getenv("SISTEM_CC_MOCK") == "1":
        return CcResult(ok=True, exit_code=0,
                        transcript=f"[MOCK CC] prompt={prompt[:60]}… cwd={cwd}",
                        stderr="", duration_ms=1, files_changed=[])
    if not secret:
        raise CcBridgeError("CC_DAEMON_SECRET not set")

    try:
        async with httpx.AsyncClient(timeout=timeout + 30) as client:
            r = await client.post(
                f"{base}/run",
                headers={"X-Auth": secret},
                json={"prompt": prompt, "cwd": cwd, "timeout": timeout,
                      "allow_edits": allow_edits, "env": env or {}},
            )
    except httpx.RequestError as e:
        raise CcBridgeError(f"cc-daemon unreachable: {e}") from e

    if r.status_code != 200:
        raise CcBridgeError(f"cc-daemon returned {r.status_code}: {r.text[:300]}")
    d = r.json()
    return CcResult(
        ok=d["ok"], exit_code=d["exit_code"], transcript=d["transcript"],
        stderr=d.get("stderr", ""), duration_ms=d["duration_ms"],
        files_changed=d.get("files_changed", []),
    )
