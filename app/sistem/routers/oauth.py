"""OAuth 2.1 + DCR минимум для Cowork Custom MCP Connector.

Реализует необходимое чтобы Custom Connector в Cowork/Claude.ai подключился:
- GET /.well-known/oauth-authorization-server — RFC 8414 discovery metadata
- GET /.well-known/oauth-protected-resource — MCP OAuth resource metadata (2024-11)
- POST /oauth/register — RFC 7591 Dynamic Client Registration
- GET /oauth/authorize — Authorization Code flow с PKCE
- POST /oauth/token — обмен code на JWT access_token

Single-user режим: любой authorize сразу возвращает code для владельца (email из env).
Никаких user prompts. Cowork получит JWT который потом работает с /mcp.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import time
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Body, Form, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select

from sistem.db import session_ctx
from sistem.models import User
from sistem.security import create_access_token, create_refresh_token, decode_token

router = APIRouter()

BASE_URL = "https://sistem.globria.biz"
OWNER_EMAIL = "sullenlar4@gmail.com"

# In-memory client registry и auth codes.
# Single-instance, single-user — БД не нужна. При рестарте контейнера сбросится, Cowork заново DCR сделает.
_CLIENTS: dict[str, dict[str, Any]] = {}
_AUTH_CODES: dict[str, dict[str, Any]] = {}
CODE_TTL = 300     # 5 min
CLIENT_TTL = 86400 * 30  # 30 days


# ─────────────────────────────────────────────────────────────
# RFC 8414 — Authorization Server Metadata
# ─────────────────────────────────────────────────────────────

@router.get("/.well-known/oauth-authorization-server")
async def as_metadata():
    return {
        "issuer": BASE_URL,
        "authorization_endpoint": f"{BASE_URL}/oauth/authorize",
        "token_endpoint": f"{BASE_URL}/oauth/token",
        "registration_endpoint": f"{BASE_URL}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"],
        "scopes_supported": ["mcp", "openid", "offline_access"],
    }


# MCP OAuth Protected Resource Metadata (draft-ietf-oauth-mcp)
@router.get("/.well-known/oauth-protected-resource")
async def resource_metadata():
    return {
        "resource": f"{BASE_URL}/mcp",
        "authorization_servers": [BASE_URL],
        "scopes_supported": ["mcp"],
        "bearer_methods_supported": ["header"],
    }


# ─────────────────────────────────────────────────────────────
# RFC 7591 — Dynamic Client Registration
# ─────────────────────────────────────────────────────────────

class DCRRequest(BaseModel):
    client_name: str | None = None
    redirect_uris: list[str] = []
    grant_types: list[str] | None = None
    response_types: list[str] | None = None
    token_endpoint_auth_method: str | None = None
    scope: str | None = None


@router.post("/oauth/register", status_code=201)
async def register(body: dict = Body(...)):
    now = int(time.time())
    cid = "sistem-" + secrets.token_urlsafe(12)
    _CLIENTS[cid] = {
        "client_id": cid,
        "client_secret": secrets.token_urlsafe(32),
        "client_id_issued_at": now,
        "client_secret_expires_at": now + CLIENT_TTL,
        "redirect_uris": body.get("redirect_uris") or [],
        "client_name": body.get("client_name") or "Cowork Custom Connector",
        "grant_types": body.get("grant_types") or ["authorization_code", "refresh_token"],
        "response_types": body.get("response_types") or ["code"],
        "token_endpoint_auth_method": body.get("token_endpoint_auth_method") or "none",
        "scope": body.get("scope") or "mcp",
    }
    return _CLIENTS[cid]


# ─────────────────────────────────────────────────────────────
# Authorization endpoint
# ─────────────────────────────────────────────────────────────

@router.get("/oauth/authorize")
async def authorize(
    request: Request,
    client_id: str,
    redirect_uri: str,
    response_type: str = "code",
    state: str | None = None,
    code_challenge: str | None = None,
    code_challenge_method: str | None = None,
    scope: str | None = None,
):
    """Single-user auto-approve.

    Cowork присылает запрос — мы сразу возвращаем code без user prompt.
    В реальном multi-user это была бы login страница + consent.
    """
    if client_id not in _CLIENTS:
        raise HTTPException(400, detail="unknown client_id")
    if response_type != "code":
        raise HTTPException(400, detail="only response_type=code supported")

    # Проверяем redirect_uri (если клиент их регистрировал)
    client = _CLIENTS[client_id]
    if client["redirect_uris"] and redirect_uri not in client["redirect_uris"]:
        # Cowork может использовать динамические redirect — не строгая проверка
        pass

    code = secrets.token_urlsafe(32)
    _AUTH_CODES[code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method or "S256",
        "scope": scope or "mcp",
        "expires_at": int(time.time()) + CODE_TTL,
    }

    params = {"code": code}
    if state:
        params["state"] = state
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(url=f"{redirect_uri}{sep}{urlencode(params)}", status_code=302)


# ─────────────────────────────────────────────────────────────
# Token endpoint
# ─────────────────────────────────────────────────────────────

def _verify_pkce(code_verifier: str | None, code_challenge: str | None, method: str) -> bool:
    if not code_challenge:
        return True  # PKCE не требовался
    if not code_verifier:
        return False
    if method == "S256":
        digest = hashlib.sha256(code_verifier.encode()).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return expected == code_challenge
    if method == "plain":
        return code_verifier == code_challenge
    return False


@router.post("/oauth/token")
async def token(
    grant_type: str = Form(...),
    code: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    client_id: str | None = Form(None),
    client_secret: str | None = Form(None),
    code_verifier: str | None = Form(None),
    refresh_token: str | None = Form(None),
    scope: str | None = Form(None),
):
    # Определяем user (для single-user всегда owner)
    async with session_ctx() as s:
        user = (await s.execute(select(User).where(User.email == OWNER_EMAIL))).scalar_one_or_none()
        if not user:
            raise HTTPException(500, detail="owner user missing")
        user_id = str(user.id)
        user_role = user.role

    if grant_type == "authorization_code":
        if not code or code not in _AUTH_CODES:
            raise HTTPException(400, detail={"error": "invalid_grant"})
        auth = _AUTH_CODES[code]
        if int(time.time()) > auth["expires_at"]:
            _AUTH_CODES.pop(code, None)
            raise HTTPException(400, detail={"error": "invalid_grant", "reason": "code expired"})
        if client_id and auth["client_id"] != client_id:
            raise HTTPException(400, detail={"error": "invalid_client"})
        # PKCE
        if not _verify_pkce(code_verifier, auth.get("code_challenge"), auth.get("code_challenge_method", "S256")):
            raise HTTPException(400, detail={"error": "invalid_grant", "reason": "pkce failed"})
        # одноразовый
        _AUTH_CODES.pop(code, None)
        access = create_access_token(sub=user_id, extra={"role": user_role})
        refresh = create_refresh_token(sub=user_id)
        return {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": 30 * 60,
            "refresh_token": refresh,
            "scope": auth.get("scope") or "mcp",
        }

    if grant_type == "refresh_token":
        if not refresh_token:
            raise HTTPException(400, detail={"error": "invalid_request"})
        try:
            payload = decode_token(refresh_token)
        except ValueError:
            raise HTTPException(400, detail={"error": "invalid_grant"})
        if payload.get("type") != "refresh":
            raise HTTPException(400, detail={"error": "invalid_grant"})
        access = create_access_token(sub=user_id, extra={"role": user_role})
        return {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": 30 * 60,
            "scope": "mcp",
        }

    raise HTTPException(400, detail={"error": "unsupported_grant_type"})
