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


class BoundedList(list, Generic[_T]):
    """A list that never exceeds *maxlen* items.

    When append/extend would exceed *maxlen* the oldest items are dropped.
    Supports ``operator.add`` for LangGraph state reducers.
    """

    def __init__(
        self,
        maxlen: int = 50,
        initlist: Optional[Union[List[_T], "BoundedList[_T]"]] = None,
    ):
        if maxlen < 1:
            raise ValueError("maxlen must be >= 1")
        self.maxlen: int = maxlen
        super().__init__(initlist or [])
        self._truncate()

    @property
    def data(self) -> List[_T]:
        return self

    def _truncate(self) -> None:
        maxlen = getattr(self, "maxlen", None)
        if maxlen is not None and len(self) > maxlen:
            self[: len(self) - maxlen] = []

    def append(self, item: _T) -> None:
        maxlen = getattr(self, "maxlen", None)
        if maxlen is not None and len(self) >= maxlen:
            self.pop(0)
        super().append(item)

    def extend(self, other: Union[List[_T], "BoundedList[_T]"]) -> None:
        items: List[_T] = list(other)
        maxlen = getattr(self, "maxlen", None)
        if maxlen is not None:
            overflow = len(self) + len(items) - maxlen
            if overflow > 0:
                del self[:overflow]
        super().extend(items)
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
            merged = BoundedList[_T](maxlen=getattr(self, "maxlen", 50), initlist=other)
            merged.extend(self)
            return merged
        return self.__add__(other)

    def copy(self) -> "BoundedList[_T]":
        return BoundedList[_T](maxlen=getattr(self, "maxlen", 50), initlist=list(self))

    def __copy__(self) -> "BoundedList[_T]":
        return self.copy()

    def __deepcopy__(self, memo: dict) -> "BoundedList[_T]":
        return BoundedList[_T](maxlen=getattr(self, "maxlen", 50), initlist=copy.deepcopy(list(self), memo))

    def to_list(self) -> List[_T]:
        return list(self)

    @classmethod
    def from_list(cls, items: List[_T], maxlen: int) -> "BoundedList[_T]":
        return cls(maxlen=maxlen, initlist=items)

    def __reduce__(self):
        return (self.__class__, (getattr(self, "maxlen", 50), list(self)))

    def __getstate__(self) -> dict:
        return {"maxlen": getattr(self, "maxlen", 50), "data": list(self)}

    def __setstate__(self, state: dict) -> None:
        self.maxlen = state.get("maxlen", 50)
        self.clear()
        super().extend(state.get("data", []))

    def __repr__(self) -> str:
        return f"BoundedList(maxlen={getattr(self, 'maxlen', 50)}, items={list(self)})"

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


_TOKEN_QUEUES: dict[str, Any] = {}


def register_token_queue(session_id: str, queue: Any) -> None:
    if session_id:
        _TOKEN_QUEUES[session_id] = queue


def unregister_token_queue(session_id: str) -> None:
    if session_id:
        _TOKEN_QUEUES.pop(session_id, None)


def get_token_queue(session_id: str) -> Optional[Any]:
    return _TOKEN_QUEUES.get(session_id) if session_id else None


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

    # Output
    final_answer: Optional[str] = None
    citations: List[dict] = Field(default_factory=list)
    is_degraded: bool = False

    # Streaming (Phase 4B) — accessed via property to avoid checkpointer serialization issues
    @property
    def _token_queue(self) -> Optional[Any]:
        return get_token_queue(self.session_id)

    @_token_queue.setter
    def _token_queue(self, q: Optional[Any]) -> None:
        if q is None:
            unregister_token_queue(self.session_id)
        else:
            register_token_queue(self.session_id, q)

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
