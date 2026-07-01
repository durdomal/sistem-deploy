"""JWT + bcrypt + AES-GCM для секретов Project Pack."""
from __future__ import annotations

import base64
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jose import JWTError, jwt
from passlib.context import CryptContext

from sistem.config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── passwords ─────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd.verify(plain, hashed)
    except Exception:
        return False


# ─── JWT ────────────────────────────────────────────────────

def create_access_token(*, sub: str, extra: dict[str, Any] | None = None) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.jwt_access_ttl_minutes)).timestamp()),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, s.jwt_private_key, algorithm=s.jwt_alg)


def create_refresh_token(*, sub: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=s.jwt_refresh_ttl_days)).timestamp()),
        "type": "refresh",
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, s.jwt_private_key, algorithm=s.jwt_alg)


def decode_token(token: str) -> dict[str, Any]:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_public_key, algorithms=[s.jwt_alg])
    except JWTError as e:
        raise ValueError(f"invalid token: {e}") from e


# ─── AES-GCM для секретов в паке ────────────────────────────

def _key_bytes() -> bytes:
    raw = get_settings().secrets_key
    try:
        b = base64.b64decode(raw, validate=True)
    except Exception:
        b = raw.encode()
    if len(b) not in (16, 24, 32):
        # если пришла произвольная строка — растянем до 32 через SHA-256
        import hashlib
        b = hashlib.sha256(b).digest()
    return b


def encrypt_secret(plain: str) -> str:
    """AES-GCM. Возвращает base64(nonce||ct)."""
    key = _key_bytes()
    aes = AESGCM(key)
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, plain.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt_secret(token: str) -> str:
    key = _key_bytes()
    aes = AESGCM(key)
    raw = base64.b64decode(token)
    nonce, ct = raw[:12], raw[12:]
    return aes.decrypt(nonce, ct, None).decode("utf-8")


SECRET_MARK = "enc:"


def encrypt_pack_secrets(pack: dict[str, Any]) -> dict[str, Any]:
    """Проходится по пути `channels.*.token`, `channels.*.bot_token`, `integrations.*` и шифрует."""
    p = json.loads(json.dumps(pack))  # deep copy
    channels = p.get("channels") or {}
    for ch_name, ch in channels.items():
        if not isinstance(ch, dict):
            continue
        for key in ("token", "bot_token"):
            val = ch.get(key)
            if isinstance(val, str) and val and not val.startswith(SECRET_MARK):
                ch[key] = SECRET_MARK + encrypt_secret(val)
    integrations = p.get("integrations") or {}
    if isinstance(integrations, dict):
        for k, v in integrations.items():
            if isinstance(v, str) and v and not v.startswith(SECRET_MARK):
                integrations[k] = SECRET_MARK + encrypt_secret(v)
    return p


def decrypt_pack_secrets(pack: dict[str, Any]) -> dict[str, Any]:
    p = json.loads(json.dumps(pack))
    channels = p.get("channels") or {}
    for ch_name, ch in channels.items():
        if not isinstance(ch, dict):
            continue
        for key in ("token", "bot_token"):
            val = ch.get(key)
            if isinstance(val, str) and val.startswith(SECRET_MARK):
                try:
                    ch[key] = decrypt_secret(val[len(SECRET_MARK):])
                except Exception:
                    ch[key] = "****DECRYPT_FAIL"
    integrations = p.get("integrations") or {}
    if isinstance(integrations, dict):
        for k, v in integrations.items():
            if isinstance(v, str) and v.startswith(SECRET_MARK):
                try:
                    integrations[k] = decrypt_secret(v[len(SECRET_MARK):])
                except Exception:
                    integrations[k] = "****DECRYPT_FAIL"
    return p


def mask_pack_secrets(pack: dict[str, Any]) -> dict[str, Any]:
    """Убирает секреты для показа наружу."""
    p = json.loads(json.dumps(pack))
    channels = p.get("channels") or {}
    for ch_name, ch in channels.items():
        if not isinstance(ch, dict):
            continue
        for key in ("token", "bot_token"):
            if ch.get(key):
                ch[key] = "****"
    integrations = p.get("integrations") or {}
    if isinstance(integrations, dict):
        for k in list(integrations.keys()):
            integrations[k] = "****"
    return p
