"""OAuth 2.1 + DCR smoke — эмулируем Cowork Custom Connector flow."""
import asyncio, base64, hashlib, os, secrets, sys, urllib.parse
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "app"))

os.environ.update({
    "SISTEM_ENV":"test",
    "DATABASE_URL":"sqlite+aiosqlite:///:memory:",
    "REDIS_URL":"redis://localhost:6379",
})
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
_k = rsa.generate_private_key(65537, 2048)
os.environ["JWT_PRIVATE_KEY"] = _k.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
os.environ["JWT_PUBLIC_KEY"] = _k.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
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
    with TestClient(app) as c:
        # 1. Discovery metadata
        r = c.get("/.well-known/oauth-authorization-server")
        assert r.status_code == 200, r.text
        meta = r.json()
        assert meta["authorization_endpoint"].endswith("/oauth/authorize")
        assert meta["token_endpoint"].endswith("/oauth/token")
        assert meta["registration_endpoint"].endswith("/oauth/register")
        assert "S256" in meta["code_challenge_methods_supported"]
        print("✓ /.well-known/oauth-authorization-server ok")

        # 2. Resource metadata
        r = c.get("/.well-known/oauth-protected-resource")
        assert r.status_code == 200
        assert "/mcp" in r.json()["resource"]
        print("✓ /.well-known/oauth-protected-resource ok")

        # 3. Dynamic Client Registration
        r = c.post("/oauth/register", json={
            "client_name": "Cowork Test",
            "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
            "grant_types": ["authorization_code", "refresh_token"],
        })
        assert r.status_code == 201, r.text
        client = r.json()
        assert client["client_id"].startswith("sistem-")
        client_id = client["client_id"]
        print(f"✓ /oauth/register → client_id={client_id[:20]}...")

        # 4. Authorize с PKCE
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        params = {
            "client_id": client_id,
            "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
            "response_type": "code",
            "state": "xyz",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": "mcp",
        }
        r = c.get("/oauth/authorize?" + urllib.parse.urlencode(params), follow_redirects=False)
        assert r.status_code == 302, r.text
        loc = r.headers["location"]
        code = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)["code"][0]
        assert code
        print(f"✓ /oauth/authorize → 302 redirect with code={code[:16]}...")

        # 5. Token exchange
        r = c.post("/oauth/token", data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
            "client_id": client_id,
            "code_verifier": verifier,
        })
        assert r.status_code == 200, r.text
        tok = r.json()
        assert tok["token_type"].lower() == "bearer"
        access = tok["access_token"]
        refresh = tok["refresh_token"]
        print(f"✓ /oauth/token → access={access[:20]}... refresh={refresh[:20]}...")

        # 6. MCP initialize через OAuth token
        r = c.post("/mcp", headers={"Authorization": f"Bearer {access}"},
                   json={"jsonrpc":"2.0","id":1,"method":"initialize","params":{}})
        assert r.status_code == 200, r.text
        assert r.json()["result"]["serverInfo"]["name"] == "sistem"
        print("✓ MCP initialize через OAuth-выданный token — работает")

        # 7. Refresh
        r = c.post("/oauth/token", data={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": client_id,
        })
        assert r.status_code == 200, r.text
        assert "access_token" in r.json()
        print("✓ refresh_token flow ok")

        # 8. PKCE неправильный verifier → отказ
        c.post("/oauth/register", json={"client_name":"t2"})
        r = c.get("/oauth/authorize?" + urllib.parse.urlencode(params), follow_redirects=False)
        code2 = urllib.parse.parse_qs(urllib.parse.urlparse(r.headers["location"]).query)["code"][0]
        r = c.post("/oauth/token", data={
            "grant_type":"authorization_code","code":code2,
            "redirect_uri":"https://claude.ai/api/mcp/auth_callback",
            "client_id":client_id,
            "code_verifier":"WRONG",
        })
        assert r.status_code == 400
        print("✓ PKCE mismatch → 400 (security)")

    print("\n=== OAuth 2.1 + DCR smoke: PASS ===")


asyncio.run(main())
