import asyncio
from typing import Optional, List, Annotated, Any
from dataclasses import dataclass, field
from pydantic import (
    BaseModel,
    Field,
    PrivateAttr,
    field_validator,
    model_serializer,
)
import operator

from backend.graph.bounded_list import BoundedList

# Default capacities for bounded lists (Phase 4D)
RETRIEVED_CHUNKS_MAXLEN = 20   # At most 20 chunks across retries
ERROR_LOG_MAXLEN = 50           # Keep last 50 error entries


@dataclass
class RetrievedChunk:
    chunk_id: str
    content: str
    score: float
    source: str
    metadata: dict = field(default_factory=dict)


@dataclass
class GenerationResult:
    answer: str
    model: str
    tokens_used: int = 0
    finish_reason: str = "stop"


def _coerce_bounded_list(v: Any, maxlen: int) -> BoundedList:
    """Convert a plain list to ``BoundedList`` if needed."""
    if isinstance(v, BoundedList):
        return v
    if isinstance(v, list):
        return BoundedList(maxlen=maxlen, initlist=v)
    raise TypeError(f"Expected list or BoundedList, got {type(v).__name__}")


class RAGState(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    # Input
    query: str = ""
    original_query: str = ""  # Raw user input preserved for memory
    history_context: str = "" # Formatted session history
    session_id: str = ""
    tenant_id: str = ""       # Tenant isolation identifier
    user_uuid: str = ""       # Immutable user UUID for audit logging

    # Processing
    rewritten_query: Optional[str] = None
    retrieved_chunks: Annotated[BoundedList[RetrievedChunk], operator.add] = Field(
        default_factory=lambda: BoundedList[RetrievedChunk](maxlen=RETRIEVED_CHUNKS_MAXLEN)
    )
    generation_result: Optional[GenerationResult] = None

    # Control flow
    retry_count: int = 0
    max_retries: int = 1
    current_phase: str = "intake"
    error_log: Annotated[BoundedList[str], operator.add] = Field(
        default_factory=lambda: BoundedList[str](maxlen=ERROR_LOG_MAXLEN)
    )

    # Critic & Evaluation
    grounding_score: float = 0.0
    is_hallucinated: bool = False
    verification_mode: str = ""  # "claims_verified", "no_claims", "extraction_failed"
    healing_target: str = ""     # Phase 3B: "none", "targeted_healing", "retrieval_expansion", "aggressive_rewrite"

    # Adaptive Retrieval (Phase 3C)
    complexity_score: float = 0.0  # [0.0, 1.0] from adaptive complexity classifier
    target_k: int = 5              # Dynamic retrieval depth set by adaptive_k()

    # Advanced Coordination
    planner_plan: Optional[dict] = None
    long_term_insights: List[str] = Field(default_factory=list)

    # Streaming (Phase 4B) — injected by stream_runner, never serialized.
    # PrivateAttr is used because asyncio.Queue is not pydantic-serializable.
    _token_queue: Optional["asyncio.Queue[str | None]"] = PrivateAttr(None)

    # Output
    final_answer: Optional[str] = None
    citations: List[dict] = Field(default_factory=list)
    is_degraded: bool = False

    # ── Pydantic serialization helpers (Phase 4D) ──────────────────────────

    @field_validator("retrieved_chunks", mode="before")
    @classmethod
    def coerce_retrieved_chunks(cls, v: Any) -> BoundedList:
        return _coerce_bounded_list(v, maxlen=RETRIEVED_CHUNKS_MAXLEN)

    @field_validator("error_log", mode="before")
    @classmethod
    def coerce_error_log(cls, v: Any) -> BoundedList:
        return _coerce_bounded_list(v, maxlen=ERROR_LOG_MAXLEN)

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        """Serialize BoundedList fields as plain lists."""
        d = handler(self)
        d["retrieved_chunks"] = self.retrieved_chunks.to_list() if isinstance(self.retrieved_chunks, BoundedList) else self.retrieved_chunks
        d["error_log"] = self.error_log.to_list() if isinstance(self.error_log, BoundedList) else self.error_log
        return d
