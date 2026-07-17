"""ORM models — the persistence backbone for the orchestrator.

A `Run` represents one end-to-end execution of an agent workflow for a user prompt.
Each `Run` has many `AgentStep`s (the trace) and produces one or more `Artifact`s
(the structured outputs — PRD in v1, designs/code/reviews in later phases).

Status enums are stored as strings so SQLite stays human-readable.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_HUMAN = "awaiting_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactKind(str, enum.Enum):
    PRD = "prd"
    CLARIFYING_QUESTIONS = "clarifying_questions"
    RESEARCH_NOTES = "research_notes"
    CRITIQUE = "critique"
    SYSTEM_DESIGN = "system_design"
    SPRINT_PLAN = "sprint_plan"
    CODE = "code"
    TEST_SUITE = "test_suite"
    VALIDATION_REPORT = "validation_report"
    REVIEW_REPORT = "review_report"


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e]),
        default=RunStatus.PENDING,
        nullable=False,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
        nullable=False,
    )

    steps: Mapped[list["AgentStep"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentStep.created_at",
        lazy="selectin",
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="Artifact.version",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_runs_status_created_at", "status", "created_at"),
    )


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node: Mapped[str] = mapped_column(String(64), nullable=False)
    agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
    )

    run: Mapped[Run] = relationship(back_populates="steps")

    __table_args__ = (
        Index("ix_agent_steps_run_id_created_at", "run_id", "created_at"),
    )


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[ArtifactKind] = mapped_column(
        Enum(ArtifactKind, native_enum=False, length=64, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
    )

    run: Mapped[Run] = relationship(back_populates="artifacts")

    __table_args__ = (
        Index("ix_artifacts_run_id_kind_version", "run_id", "kind", "version"),
    )
