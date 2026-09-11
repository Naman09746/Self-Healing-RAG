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
import copy
from collections import UserList
from typing import (
    Generic,
    Iterator,
    overload,
    TypeVar,
    Union,
)

_T = TypeVar("_T")


class BoundedList(UserList[_T], Generic[_T]):
    """A list that never exceeds *maxlen* items.

    When append/extend would exceed *maxlen* the oldest items are dropped.
    Supports ``operator.add`` for LangGraph state reducers.
    """

    def __init__(
        self,
        maxlen: int,
        initlist: Optional[Union[List[_T], "BoundedList[_T]"]] = None,
    ):
        if maxlen < 1:
            raise ValueError("maxlen must be >= 1")
        self.maxlen: int = maxlen
        super().__init__(initlist or [])
        self._truncate()

    def _truncate(self) -> None:
        if len(self.data) > self.maxlen:
            self.data[: len(self.data) - self.maxlen] = []

    def append(self, item: _T) -> None:
        if len(self.data) >= self.maxlen:
            self.data.pop(0)
        self.data.append(item)

    def extend(self, other: Union[List[_T], "BoundedList[_T]"]) -> None:
        items: List[_T] = list(other)
        overflow = len(self.data) + len(items) - self.maxlen
        if overflow > 0:
            del self.data[:overflow]
        self.data.extend(items)
        self._truncate()

    def __iadd__(self, other: Union[List[_T], "BoundedList[_T]"]) -> "BoundedList[_T]":
        self.extend(other)
        return self

    def __add__(self, other: Union[List[_T], "BoundedList[_T]"]) -> "BoundedList[_T]":
        new = self.copy()
        new.extend(other)
        return new

    def __radd__(self, other: Union[List[_T], "BoundedList[_T]"]) -> "BoundedList[_T]":
        if isinstance(other, list):
            merged = BoundedList[_T](maxlen=self.maxlen, initlist=other)
            merged.extend(self)
            return merged
        return self.__add__(other)

    def copy(self) -> "BoundedList[_T]":
        return BoundedList[_T](maxlen=self.maxlen, initlist=list(self.data))

    def __copy__(self) -> "BoundedList[_T]":
        return self.copy()

    def __deepcopy__(self, memo: dict) -> "BoundedList[_T]":
        return BoundedList[_T](maxlen=self.maxlen, initlist=copy.deepcopy(self.data, memo))

    def to_list(self) -> List[_T]:
        return list(self.data)

    @classmethod
    def from_list(cls, items: List[_T], maxlen: int) -> "BoundedList[_T]":
        return cls(maxlen=maxlen, initlist=items)

    def __getstate__(self) -> dict:
        return {"maxlen": self.maxlen, "data": self.data}

    def __setstate__(self, state: dict) -> None:
        self.maxlen = state["maxlen"]
        self.data = state["data"]

    def __repr__(self) -> str:
        return f"BoundedList(maxlen={self.maxlen}, items={list(self.data)})"

    def __str__(self) -> str:
        return repr(self)


# Default capacities for bounded lists
RETRIEVED_CHUNKS_MAXLEN = 20
ERROR_LOG_MAXLEN = 50


@dataclass
class RetrievedChunk:
    chunk_id: str
    content: str
    score: float
    source: str
    metadata: dict = field(default_factory=dict)
    distance: Optional[float] = None


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
    no_relevant_chunks: bool = False
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
