"""Кросс-СУБД типы. Используем общие sqlalchemy.JSON/String — работают и в PG, и в SQLite.

Для prod с asyncpg JSON эмулируется как JSONB (asyncpg сам умеет). Для тестов SQLite — как TEXT/JSON.
Если понадобятся PG-специфичные операторы (@>, ?), делаем hybrid_method или raw SQL.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import JSON, String, TypeDecorator
from sqlalchemy.dialects.postgresql import INET as PG_INET, UUID as PG_UUID


class UUID_(TypeDecorator):
    """UUID → нативный PG ``uuid`` в проде (asyncpg), TEXT(36) в SQLite. Возвращает uuid.UUID.

    ВАЖНО: db/schema.sql объявляет id/user_id как нативный ``uuid``. Если биндить
    значение как строку (String), Postgres бьёт
    ``operator does not exist: uuid = character varying`` на КАЖДОМ запросе с фильтром
    по id. Поэтому в PG используем нативный тип (bind — uuid.UUID), в SQLite — TEXT(36).
    """
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value: Any, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
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

class INET_(TypeDecorator):
    """inet → нативный PG ``inet`` в проде, String(45) в SQLite (тесты).

    audit_log.ip объявлен как ``inet``. String-бинд ломает INSERT:
    ``column "ip" is of type inet but expression is of type character varying``
    (даже для NULL — тип выражения не совпадает).
    """
    impl = String(45)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_INET())
        return dialect.type_descriptor(String(45))
