import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, JSON, DateTime, Boolean, Text, ForeignKey, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # Immutable UUID assigned at creation — used as tenant_id throughout the system
    user_uuid = Column(String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    role = Column(String, default="viewer", nullable=False)
    tenant_id = Column(String, default="default", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Document(Base):
    """Tracks ingested documents with tenant scoping."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String(64), unique=True, index=True, nullable=False)
    tenant_id = Column(String, index=True, nullable=False)
    filename = Column(String, nullable=False)
    chunk_count = Column(Integer, default=0)
    content_hash = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """Immutable audit trail for retrieval operations."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True, nullable=False)
    user_uuid = Column(String(36), nullable=True)
    session_id = Column(String, index=True)
    operation = Column(String(32), nullable=False)  # e.g., "retrieve", "ingest", "delete"
    query_text_hash = Column(String(64))
    chunk_count = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class ExecutionTrace(Base):
    __tablename__ = "execution_traces"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    query = Column(String)
    phase = Column(String)
    agent_name = Column(String)
    input_data = Column(JSON)
    output_data = Column(JSON)
    latency_ms = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    is_error = Column(Boolean, default=False)
    tokens_used = Column(Integer, default=0)


class EvaluationMetric(Base):
    __tablename__ = "evaluation_metrics"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    grounding_score = Column(Float)
    answer_relevance = Column(Float)
    faithfulness = Column(Float)
    retrieval_precision = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)