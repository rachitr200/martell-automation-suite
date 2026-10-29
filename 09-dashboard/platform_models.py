"""Persistent operations records. No secrets are stored in these tables."""
from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base, utcnow


class UserSession(Base):
    __tablename__ = 'platform_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor: Mapped[str] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(20))
    expires: Mapped[int] = mapped_column(Integer)


class CopilotRun(Base):
    __tablename__ = 'platform_runs'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor: Mapped[str] = mapped_column(String(150))
    mode: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default='running')
    question: Mapped[str] = mapped_column(Text)
    customer_id: Mapped[str] = mapped_column(String(255))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    trace: Mapped[list] = mapped_column(JSON, default=list)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEntry(Base):
    __tablename__ = 'platform_audit'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor: Mapped[str] = mapped_column(String(150))
    action: Mapped[str] = mapped_column(String(100))
    target: Mapped[str] = mapped_column(String(255))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeChunk(Base):
    __tablename__ = 'platform_knowledge'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvalResult(Base):
    __tablename__ = 'platform_evals'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConnectorReceipt(Base):
    __tablename__ = 'platform_connector_receipts'
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    source: Mapped[str] = mapped_column(String(30))
    kind: Mapped[str] = mapped_column(String(100))
    summary: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class RecoveryJob(Base):
    __tablename__ = 'platform_recovery_jobs'
    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    available_at: Mapped[int] = mapped_column(Integer)
