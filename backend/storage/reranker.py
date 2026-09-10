"""Backward-compatible shim — delegates to pluggable factory. Prefer `from backend.storage.reranker.factory import get_reranker`."""

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Keep legacy class alias for type hints
try:
    from backend.storage.reranker.cross_encoder import CrossEncoderReranker as Reranker  # noqa: F401
except Exception:
    from backend.storage.reranker.none import NoOpReranker as Reranker  # type: ignore

# Singleton via factory (free-tier default = none)
try:
    from backend.storage.reranker.factory import get_reranker

    reranker = get_reranker()
except Exception as e:
    logger.warning("Could not init reranker via factory, using NoOp", error=str(e))
    from backend.storage.reranker.none import NoOpReranker

    reranker = NoOpReranker()  # type: ignore
