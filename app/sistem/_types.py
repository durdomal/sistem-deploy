"""Кросс-СУБД типы. Используем общие sqlalchemy.JSON/String — работают и в PG, и в SQLite.

Для prod с asyncpg JSON эмулируется как JSONB (asyncpg сам умеет). Для тестов SQLite — как TEXT/JSON.
Если понадобятся PG-специфичные операторы (@>, ?), делаем hybrid_method или raw SQL.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import JSON, String, TypeDecorator


class UUID_(TypeDecorator):
    """UUID → PG UUID в проде, TEXT(36) в SQLite. Возвращает uuid.UUID."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(value)

    def process_result_value(self, value: Any, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(value)
        except Exception:
            return value


# JSONB → JSON (эквивалент для наших целей)
JSONB_ = JSON

# ARRAY(Text) → JSON (список строк)
ARRAY_ = JSON

# UUIDArray → JSON (список строк)
UUIDArray_ = JSON

# INET → String(45)
INET_ = String
