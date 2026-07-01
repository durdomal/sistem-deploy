"""Sprint 3 smoke — CC bridge MOCK."""
import asyncio, os, sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "app"))
os.environ.update({
    "SISTEM_ENV":"test",
    "DATABASE_URL":"sqlite+aiosqlite:///:memory:",
    "REDIS_URL":"redis://localhost:6379",
    "SISTEM_CC_MOCK":"1",
})
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
_k = rsa.generate_private_key(65537, 2048)
os.environ["JWT_PRIVATE_KEY"] = _k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
os.environ["JWT_PUBLIC_KEY"] = _k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
import base64
os.environ["SISTEM_SECRETS_KEY"] = base64.b64encode(os.urandom(32)).decode()
os.environ["SISTEM_BOOTSTRAP_PASSWORD"] = "test-password-123"

async def main():
    from sistem.db import session_ctx
    from sistem.models import Base
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sistem.services.bootstrap import bootstrap
    import sistem.db as db_mod
    engine = create_async_engine(os.environ["DATABASE_URL"], future=True)
    db_mod._engine = engine
    db_mod._SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    async with session_ctx() as s: await bootstrap(s)

    from fastapi.testclient import TestClient
    from sistem.main import app
    import json
    with TestClient(app) as c:
        r = c.post("/auth/login", json={"email":"sullenlar4@gmail.com","password":"test-password-123"})
        H = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = c.post("/bridge/cc/run", headers=H, json={"prompt":"index the repo with graphify","cwd":"globria"})
        assert r.status_code == 200, r.text
        assert "[MOCK CC]" in r.json()["transcript"]
        print("✓ POST /bridge/cc/run (mock) works")
        r = c.post("/mcp", headers=H, json={"jsonrpc":"2.0","id":1,"method":"tools/call",
                                             "params":{"name":"sistem_run_claude_code",
                                                       "arguments":{"prompt":"say hi","cwd":"tmp"}}})
        d = json.loads(r.json()["result"]["content"][0]["text"])
        assert d["ok"] and "[MOCK CC]" in d["transcript"]
        print("✓ MCP sistem_run_claude_code (mock) works")
    print("\n=== Sprint 3 smoke: PASS ===")

asyncio.run(main())
