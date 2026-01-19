"""SQLAlchemy ORM models for the conversation generation service.

This module defines database models for:
- SceneAnalysisLog: Scene analysis results
- PersonaSnapshotModel: User persona snapshots
- LLMCallLog: LLM call records for billing
- IntimacyCheckLog: Intimacy check results
- GenerationResultModel: Final generation results
"""

from datetime import datetime
from typing import Any, Dict

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Dialog(Base):
    """record of dialog"""
    __tablename__ = "dialogs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    dialogs: Mapped[list[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)


class ConversationSummaryLog(Base):
    __tablename__ = "conversation_summary_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class SceneAnalysisLog(Base):
    """Log of scene analysis results."""

    __tablename__ = "scene_analysis_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scene: Mapped[str] = mapped_column(String(50), nullable=False)
    intimacy_level: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_flags: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class PersonaSnapshotModel(Base):
    """Snapshot of inferred user persona."""

    __tablename__ = "persona_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    style: Mapped[str] = mapped_column(String(50), nullable=False)
    pacing: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_tolerance: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class LLMCallLog(Base):
    """Log of LLM API calls for billing and monitoring."""

    __tablename__ = "llm_call_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class IntimacyCheckLog(Base):
    """Log of intimacy check results."""

    __tablename__ = "intimacy_check_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    reply_text: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class GenerationResultModel(Base):
    """Final generation result record."""

    __tablename__ = "generation_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    reply_text: Mapped[str] = mapped_column(Text, nullable=False)
    intimacy_before: Mapped[int] = mapped_column(Integer, nullable=False)
    intimacy_after: Mapped[int] = mapped_column(Integer, nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
