"""Smoke-тест Sprint 1: auth → создание Watersports pack → /command → tasks → skills.

Использует SQLite in-memory (без Postgres/Redis) — валидирует бизнес-логику.
В проде тот же код работает с asyncpg + Redis.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import yaml

# ─ подложим тестовые env-переменные ДО импорта sistem ────────
BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "app"))

os.environ["SISTEM_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379"

# Генерим тестовые JWT-ключи
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
os.environ["JWT_PRIVATE_KEY"] = _key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()
os.environ["JWT_PUBLIC_KEY"] = _key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode()

import base64  # noqa: E402
os.environ["SISTEM_SECRETS_KEY"] = base64.b64encode(os.urandom(32)).decode()
os.environ["SISTEM_BOOTSTRAP_PASSWORD"] = "test-password-123"

# Кросс-СУБД типы уже в моделях (sistem/_types.py) — доп. патчей не нужно.


async def main():
    # Импортируем ПОСЛЕ подмены env
    from sistem.db import _init as db_init, session_ctx  # type: ignore
    from sistem.models import Base
    from sqlalchemy.ext.asyncio import create_async_engine
    from sistem.services.bootstrap import bootstrap

    # Инитим SQLite движок вручную (обходя lazy init)
    import sistem.db as db_mod
    engine = create_async_engine(os.environ["DATABASE_URL"], future=True)
    from sqlalchemy.ext.asyncio import async_sessionmaker
    db_mod._engine = engine
    db_mod._SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    # Создаём схему
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_ctx() as s:
        await bootstrap(s)

    print("✓ bootstrap done")

    # ─ HTTP тесты ─
    from fastapi.testclient import TestClient
    from sistem.main import app

    with TestClient(app) as c:
        # health/status
        r = c.get("/health")
        assert r.status_code == 200
        print("✓ /health", r.json()["version"])
        r = c.get("/status")
        print("✓ /status", r.json()["components"])

        # login
        r = c.post("/auth/login", json={"email": "sullenlar4@gmail.com", "password": "test-password-123"})
        assert r.status_code == 200, r.text
        tokens = r.json()
        access = tokens["access_token"]
        H = {"Authorization": f"Bearer {access}"}
        print("✓ /auth/login ok")

        # get uid from access token
        from sistem.security import decode_token
        uid = decode_token(access)["sub"]

        # список проектов пустой
        r = c.get(f"/users/{uid}/projects", headers=H)
        assert r.status_code == 200
        assert r.json() == []
        print("✓ empty projects list")

        # создаём watersports-cb
        pack = yaml.safe_load((BASE / "examples" / "watersports-cb.pack.yaml").read_text(encoding="utf-8"))
        # добавим секрет в channel — проверить шифрование
        pack.setdefault("channels", {}).setdefault("instagram", {})["token"] = "SUPER_SECRET_IG_TOKEN"

        r = c.post(f"/users/{uid}/projects", headers=H, json=pack)
        assert r.status_code == 201, r.text
        got = r.json()
        assert got["slug"] == "watersports-cb"
        assert got["pack"]["channels"]["instagram"]["token"] == "****", "секрет должен быть замаскирован в ответе"
        print("✓ project created, secret masked")

        # получение проекта с секретами
        r = c.get(f"/users/{uid}/projects/watersports-cb?include_secrets=true", headers=H)
        assert r.status_code == 200
        assert r.json()["pack"]["channels"]["instagram"]["token"] == "SUPER_SECRET_IG_TOKEN"
        print("✓ decrypt on request ok")

        # проверка валидации (плохой пак)
        bad = {"project": {"id": "bad"}}
        r = c.post(f"/users/{uid}/projects", headers=H, json=bad)
        assert r.status_code == 422
        print("✓ validation rejects bad pack")

        # список скиллов
        r = c.get("/skills")
        assert r.status_code == 200
        names = {s["name"] for s in r.json()}
        for expected in ("marketing-audit", "content-reels", "kpi-report", "content-distribution", "web-studio-orchestrator"):
            assert expected in names, f"missing {expected}"
        print(f"✓ /skills returns {len(names)} registered skills")

        # /command — «сделай рилс для проекта watersports-cb»
        r = c.post(
            "/command",
            headers=H,
            json={"text": "сделай рилс про новый SUP-борд для проекта watersports-cb"},
        )
        assert r.status_code == 200, r.text
        resp = r.json()
        assert resp["resolved_skill"] == "content-reels"
        assert resp["project_id"] == "watersports-cb"
        task_id = resp["task_id"]
        print(f"✓ /command resolved → content-reels for watersports-cb, task {task_id[:8]}…")

        # /command dry-run
        r = c.post("/command", headers=H, json={"text": "аудит бизнеса", "execute": False})
        assert r.status_code == 200
        assert r.json()["queued"] is False
        assert r.json()["resolved_skill"] == "marketing-audit"
        print("✓ /command dry-run ok")

        # memory — добавим и найдём
        r = c.post(f"/users/{uid}/memory/universal", headers=H, json={
            "kind": "preference",
            "title": "Отвечать по-русски",
            "body": "Тарас предпочитает короткие ответы на русском.",
            "tags": ["language", "preference"],
        })
        assert r.status_code == 201, r.text
        r = c.get(f"/users/{uid}/memory/universal?query=русск", headers=H)
        assert r.status_code == 200 and len(r.json()) == 1
        print("✓ memory add + query ok")

        # добавим в память проекта
        r = c.post(f"/users/{uid}/memory/projects/watersports-cb", headers=H, json={
            "kind": "fact", "title": "Season", "body": "Летний пик — июль-август.",
        })
        assert r.status_code == 201
        r = c.get(f"/users/{uid}/memory/projects/watersports-cb", headers=H)
        assert len(r.json()) == 1
        print("✓ project memory ok")

        # MCP — initialize
        r = c.post("/mcp", headers=H, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert r.status_code == 200 and r.json()["result"]["serverInfo"]["name"] == "sistem"
        print("✓ MCP initialize ok")

        # MCP — tools/list
        r = c.post("/mcp", headers=H, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        assert r.status_code == 200
        assert len(r.json()["result"]["tools"]) == 10
        print(f"✓ MCP tools/list → 10 tools")

        # MCP — sistem_status
        r = c.post("/mcp", headers=H, json={
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "sistem_status", "arguments": {}},
        })
        assert r.status_code == 200
        content = json.loads(r.json()["result"]["content"][0]["text"])
        assert content["count"] == 1
        print("✓ MCP sistem_status ok")

        # MCP — sistem_command
        r = c.post("/mcp", headers=H, json={
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "sistem_command", "arguments": {
                "text": "сделай маркетинг-аудит для проекта watersports-cb"
            }},
        })
        assert r.status_code == 200
        r_data = json.loads(r.json()["result"]["content"][0]["text"])
        assert r_data["resolved_skill"] == "marketing-audit"
        print(f"✓ MCP sistem_command → marketing-audit, task {r_data['task_id'][:8]}…")

        # MCP — sistem_project_context
        r = c.post("/mcp", headers=H, json={
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {"name": "sistem_project_context", "arguments": {"project_id": "watersports-cb"}},
        })
        pc = json.loads(r.json()["result"]["content"][0]["text"])
        assert pc["slug"] == "watersports-cb"
        assert pc["pack"]["channels"]["instagram"]["token"] == "****"
        print("✓ MCP sistem_project_context ok (secrets masked)")

    print("\n=== Sprint 1 smoke: PASS ===")


if __name__ == "__main__":
    asyncio.run(main())
