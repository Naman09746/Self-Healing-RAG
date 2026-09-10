"""Factory for reranker."""

from __future__ import annotations

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


def get_reranker():
    provider = (getattr(settings, "RERANKER_PROVIDER", "none") or "none").lower().strip()
    model_name = getattr(settings, "RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    logger.info("Initializing reranker", provider=provider)

    if provider == "cross-encoder":
        try:
            from backend.storage.reranker.cross_encoder import CrossEncoderReranker

            return CrossEncoderReranker(model_name=model_name)
        except Exception as e:
            logger.error("Failed to init CrossEncoderReranker, falling back to none", error=str(e))

    if provider == "cohere":
        # Cohere API reranker — optional, requires COHERE_API_KEY
        try:
            from backend.storage.reranker.cohere import CohereReranker  # type: ignore

            return CohereReranker(api_key=getattr(settings, "COHERE_API_KEY", ""))
        except Exception as e:
            logger.error("Failed to init CohereReranker, falling back to none", error=str(e))

    from backend.storage.reranker.none import NoOpReranker

    return NoOpReranker()
