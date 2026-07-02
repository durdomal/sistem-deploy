"""Sistem Core — FastAPI entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sistem import __version__
from sistem.config import get_settings
from sistem.db import ping as db_ping, session_ctx
from sistem.services.bootstrap import bootstrap as bootstrap_defaults
from sistem.services.queue import get_redis
from sistem.routers import auth, bridges, command, mcp, memory, oauth, projects, skills, system

log = logging.getLogger("sistem")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log.info("Sistem Core %s starting (env=%s)", __version__, settings.env)
    if settings.env != "test":
        try:
            async with session_ctx() as s:
                await bootstrap_defaults(s)
        except Exception as e:
            log.warning("Bootstrap skipped: %s", e)
    yield
    log.info("Sistem Core shutting down")


app = FastAPI(
    title="Sistem Core",
    version=__version__,
    description="Universal AI-OS for entrepreneurs. See /docs.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://sistem.globria.biz"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"ok": True, "version": __version__, "time": datetime.now(timezone.utc).isoformat()}


@app.get("/status", tags=["system"])
async def status() -> dict:
    db_ok = await db_ping()
    redis_ok = False
    try:
        redis_ok = bool(get_redis().ping())
    except Exception:
        redis_ok = False
    return {
        "ok": True,
        "version": __version__,
        "components": {
            "api": "up",
            "db": "up" if db_ok else "down",
            "redis": "up" if redis_ok else "down",
        },
        "time": datetime.now(timezone.utc).isoformat(),
    }


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(projects.router, prefix="/users/{uid}/projects", tags=["projects"])
app.include_router(memory.router, prefix="/users/{uid}/memory", tags=["memory"])
app.include_router(command.router, tags=["command"])
app.include_router(skills.router, prefix="/skills", tags=["skills"])
app.include_router(bridges.router, prefix="/bridge", tags=["bridges"])
app.include_router(system.router, tags=["system"])
app.include_router(mcp.router, prefix="/mcp", tags=["mcp"])
app.include_router(oauth.router, tags=["oauth"])


@app.exception_handler(Exception)
async def unhandled(_, exc):
    log.exception("Unhandled: %s", exc)
    return JSONResponse(status_code=500, content={"ok": False, "error": "internal"})
