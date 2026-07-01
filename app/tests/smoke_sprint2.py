"""Smoke Sprint 2: подключаем VPS bridge (MOCK) + n8n bridge (MOCK) поверх Sprint 1.

MOCK-режимы: SISTEM_VPS_MOCK=1, SISTEM_N8N_MOCK=1.
"""
from __future__ import annotations
import asyncio, os, sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "app"))

os.environ["SISTEM_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["SISTEM_VPS_MOCK"] = "1"
os.environ["SISTEM_N8N_MOCK"] = "1"

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
os.environ["JWT_PRIVATE_KEY"] = _key.private_bytes(
    encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()).decode()
os.environ["JWT_PUBLIC_KEY"] = _key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo).decode()

import base64
os.environ["SISTEM_SECRETS_KEY"] = base64.b64encode(os.urandom(32)).decode()
os.environ["SISTEM_BOOTSTRAP_PASSWORD"] = "test-password-123"


async def main():
    from sistem.db import session_ctx
    from sistem.models import Base, BridgeN8nWorkflow, User
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sistem.services.bootstrap import bootstrap
    from sqlalchemy import select

    import sistem.db as db_mod
    engine = create_async_engine(os.environ["DATABASE_URL"], future=True)
    db_mod._engine = engine
    db_mod._SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with session_ctx() as s:
        await bootstrap(s)
        # регистрируем тестовый n8n workflow
        user = (await s.execute(select(User).where(User.email == "sullenlar4@gmail.com"))).scalar_one()
        s.add(BridgeN8nWorkflow(user_id=user.id, workflow_id="daily-server-health",
                                name="Daily Server Health",
                                webhook_url="https://n8n.globria.biz/webhook/sistem/daily-server-health",
                                description="mock test"))
        await s.commit()

    from fastapi.testclient import TestClient
    from sistem.main import app

    with TestClient(app) as c:
        r = c.post("/auth/login", json={"email": "sullenlar4@gmail.com", "password": "test-password-123"})
        assert r.status_code == 200
        access = r.json()["access_token"]
        H = {"Authorization": f"Bearer {access}"}

        # /skills теперь содержит v0.3 скиллы
        r = c.get("/skills")
        assert r.status_code == 200
        names = {s["name"] for s in r.json()}
        for n in ("booking-agent","connector-setup","retainer-agency","unit-economics","sell-sites-localbiz"):
            assert n in names, f"missing v0.3 skill {n}"
        print(f"✓ /skills has {len(names)} incl. v0.3")

        # VPS bridge — allow-listed команда (uptime — в default allow_cmds)
        r = c.post("/bridge/vps/152.53.231.15/run", headers=H, json={"cmd": "uptime"})
        assert r.status_code == 200 and r.json()["ok"]
        assert "[MOCK]" in r.json()["stdout"]
        print("✓ VPS bridge allow → OK (mock)")

        # VPS bridge — запрещённая команда
        r = c.post("/bridge/vps/152.53.231.15/run", headers=H, json={"cmd": "rm -rf /"})
        assert r.status_code == 400
        assert "allowlist" in r.json()["detail"]
        print("✓ VPS bridge deny → 400 (allowlist)")

        # VPS bridge — незарегистрированный хост
        r = c.post("/bridge/vps/some-other-host/run", headers=H, json={"cmd": "uptime"})
        assert r.status_code == 400
        assert "not registered" in r.json()["detail"]
        print("✓ VPS bridge unknown host → 400")

        # n8n bridge — mock
        r = c.post("/bridge/n8n/trigger/daily-server-health", headers=H, json={"payload": {"foo": "bar"}})
        assert r.status_code == 200, r.text
        assert r.json()["ok"] and r.json()["payload"]["mock"] is True
        print("✓ n8n trigger → OK (mock)")

        # MCP tools/list — 10 тулов, но теперь run_on_vps и trigger_n8n не заглушки
        r = c.post("/mcp", headers=H, json={"jsonrpc":"2.0","id":1,"method":"tools/call",
                                             "params":{"name":"sistem_run_on_vps",
                                                       "arguments":{"host":"152.53.231.15","cmd":"uptime"}}})
        assert r.status_code == 200
        import json
        data = json.loads(r.json()["result"]["content"][0]["text"])
        assert data["ok"] and "[MOCK]" in data["stdout"]
        print("✓ MCP sistem_run_on_vps (mock) works")

        r = c.post("/mcp", headers=H, json={"jsonrpc":"2.0","id":2,"method":"tools/call",
                                             "params":{"name":"sistem_trigger_n8n",
                                                       "arguments":{"workflow":"daily-server-health","payload":{}}}})
        assert r.status_code == 200
        data = json.loads(r.json()["result"]["content"][0]["text"])
        assert data["ok"] and data["payload"]["mock"] is True
        print("✓ MCP sistem_trigger_n8n (mock) works")

    print("\n=== Sprint 2 smoke: PASS ===")


asyncio.run(main())
