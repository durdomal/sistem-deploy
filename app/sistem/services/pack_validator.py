"""Валидация Project Pack по JSON Schema."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_SCHEMA_CACHE: dict[str, Any] | None = None


def _load() -> dict[str, Any]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE
    # ищем относительно /app
    for p in [
        Path(__file__).resolve().parents[3] / "schemas" / "project-pack.schema.json",
        Path("/opt/sistem/schemas/project-pack.schema.json"),
        Path("schemas/project-pack.schema.json"),
    ]:
        if p.exists():
            _SCHEMA_CACHE = json.loads(p.read_text())
            return _SCHEMA_CACHE
    raise FileNotFoundError("project-pack.schema.json not found")


def validate_pack(pack: dict[str, Any]) -> list[str]:
    """Возвращает список текстовых ошибок; пустой список — валидный."""
    v = Draft202012Validator(_load())
    return [f"{list(e.absolute_path) or '<root>'}: {e.message}" for e in v.iter_errors(pack)]
