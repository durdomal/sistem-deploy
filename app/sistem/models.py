"""SQLAlchemy 2.0 модели — соответствуют db/schema.sql."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from sistem._types import ARRAY_ as ARRAY, INET_ as INET, JSONB_ as JSONB, UUIDArray_ as UUIDArray, UUID_ as UUID


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(), primary_key=True, default=uuid.uuid4)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="owner")
    locale: Mapped[str] = mapped_column(Text, default="ru")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_projects_user_slug"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    niche: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    pack: Mapped[dict[str, Any]] = mapped_column(JSONB(), nullable=False)
    pack_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemoryUniversal(Base):
    __tablename__ = "memory_universal"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemoryProject(Base):
    __tablename__ = "memory_project"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(), default=list)
    source: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemoryInsight(Base):
    __tablename__ = "memory_insights"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    projects: Mapped[list[uuid.UUID]] = mapped_column(UUIDArray(), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(3, 2))
    generated_by: Mapped[Optional[str]] = mapped_column(Text)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False, default="1.0")
    description: Mapped[Optional[str]] = mapped_column(Text)
    input_schema: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB())
    output_schema: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB())
    handler: Mapped[str] = mapped_column(Text, nullable=False)
    project_agnostic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(), ForeignKey("projects.id", ondelete="SET NULL"))
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_skill: Mapped[Optional[str]] = mapped_column(Text)
    resolved_params: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB())
    bridge: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB())
    error: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(), ForeignKey("users.id", ondelete="SET NULL"))
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(), ForeignKey("projects.id", ondelete="SET NULL"))
    task_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(), ForeignKey("tasks.id", ondelete="SET NULL"))
    event: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB())
    ip: Mapped[Optional[str]] = mapped_column(INET())
    ua: Mapped[Optional[str]] = mapped_column(Text)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BridgeVpsHost(Base):
    __tablename__ = "bridge_vps_hosts"
    __table_args__ = (UniqueConstraint("user_id", "host", name="uq_bridge_vps_user_host"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    host: Mapped[str] = mapped_column(Text, nullable=False)
    ssh_user: Mapped[str] = mapped_column(Text, nullable=False)
    ssh_key_ref: Mapped[str] = mapped_column(Text, nullable=False)
    allow_cmds: Mapped[list[str]] = mapped_column(ARRAY(), default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BridgePc(Base):
    __tablename__ = "bridge_pcs"
    __table_args__ = (UniqueConstraint("user_id", "pc_id", name="uq_bridge_pc_user_pcid"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    pc_id: Mapped[str] = mapped_column(Text, nullable=False)
    tunnel_url: Mapped[Optional[str]] = mapped_column(Text)
    public_key_pem: Mapped[Optional[str]] = mapped_column(Text)
    allow_cmds: Mapped[list[str]] = mapped_column(ARRAY(), default=list)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BridgeN8nWorkflow(Base):
    __tablename__ = "bridge_n8n_workflows"
    __table_args__ = (UniqueConstraint("user_id", "workflow_id", name="uq_bridge_n8n_user_wf"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    workflow_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    webhook_url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(Text, nullable=False, default="personal")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    stripe_customer: Mapped[Optional[str]] = mapped_column(Text)
    stripe_sub_id: Mapped[Optional[str]] = mapped_column(Text)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
