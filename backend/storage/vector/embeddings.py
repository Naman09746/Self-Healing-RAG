"""Embedding provider abstraction — decouples vector stores from Ollama/Chroma embedding_functions."""

from __future__ import annotations

import hashlib
import math

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

try:
    import ollama  # type: ignore
except Exception:  # pragma: no cover
    ollama = None  # type: ignore


class EmbeddingError(RuntimeError):
    pass


def _ollama_embed(texts: list[str], model: str, host: str) -> list[list[float]]:
    """Call Ollama /api/embeddings synchronously."""
    if ollama is None:
        raise EmbeddingError("ollama package not available")
    client = ollama.Client(host=host)
    vectors: list[list[float]] = []
    for t in texts:
        resp = client.embeddings(model=model, prompt=t)
        vec = resp.get("embedding")
        if vec is None:
            # fallback for newer client where key is 'embeddings'
            vec = resp.get("embeddings") or resp.get("data")
        if vec is None:
            raise EmbeddingError(f"Ollama embeddings returned no vector for text prefix: {t[:60]}")
        # ollama can return nested list
        if isinstance(vec[0], list):
            vec = vec[0]
        vectors.append([float(x) for x in vec])
    return vectors


def _openai_embed(texts: list[str], model: str, api_key: str, base_url: str | None) -> list[list[float]]:
    """Call OpenAI-compatible embeddings API."""
    try:
        from openai import OpenAI
    except Exception as e:
        raise EmbeddingError(f"openai package required for OPENAI embeddings: {e}") from e
    kwargs: dict = {}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(api_key=api_key, **kwargs)
    resp = client.embeddings.create(model=model, input=texts)
    return [list(d.embedding) for d in resp.data]


def _hash_embed(texts: list[str], dim: int) -> list[list[float]]:
    """Deterministic hash-based fallback for tests / offline mode.

    Uses SHA256 to generate pseudo-embeddings with unit norm. Not useful for
    production retrieval quality but guarantees deterministic behaviour when
    Ollama/OpenAI are unavailable.
    """
    vectors: list[list[float]] = []
    for t in texts:
        h = hashlib.sha256(t.encode("utf-8")).digest()
        # expand to dim
        vals: list[float] = []
        while len(vals) < dim:
            h = hashlib.sha256(h).digest()
            vals.extend([b / 255.0 for b in h])
        vals = vals[:dim]
        norm = math.sqrt(sum(v * v for v in vals)) or 1.0
        vectors.append([v / norm for v in vals])
    return vectors


class EmbeddingProvider:
    """Unified embedding provider used by all vector stores."""

    def __init__(
        self,
        model: str | None = None,
        dim: int | None = None,
        use_hash_fallback: bool = True,
    ):
        self.model = model or getattr(settings, "EMBEDDING_MODEL", "nomic-embed-text")
        self.dim = dim or getattr(settings, "VECTOR_STORE_DIM", 768)
        self.use_hash_fallback = use_hash_fallback
        self._provider = (getattr(settings, "LLM_PROVIDER", "ollama") or "ollama").lower()
        self._ollama_host = getattr(settings, "OLLAMA_HOST", "http://localhost:11434")
        self._openai_key = getattr(settings, "OPENAI_API_KEY", "") or ""
        self._openai_url = getattr(settings, "OPENAI_BASE_URL", "") or None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # Prefer OpenAI-compatible if configured for non-ollama or key present
        if self._openai_key and self._provider in ("openai", "groq", "openrouter"):
            try:
                vecs = _openai_embed(texts, self.model, self._openai_key, self._openai_url)
                self._validate_dim(vecs)
                return vecs
            except Exception as e:
                logger.warning("OpenAI embeddings failed, falling back", error=str(e))
                if not self.use_hash_fallback:
                    raise
        # Ollama
        try:
            if ollama is not None:
                vecs = _ollama_embed(texts, self.model, self._ollama_host)
                self._validate_dim(vecs)
                return vecs
        except Exception as e:
            logger.warning("Ollama embeddings failed, falling back to hash", error=str(e))
            if not self.use_hash_fallback:
                raise
        if self.use_hash_fallback:
            logger.warning("Using deterministic hash embeddings (offline/test mode)", dim=self.dim, count=len(texts))
            return _hash_embed(texts, self.dim)
        raise EmbeddingError("No embedding provider available and hash fallback disabled")

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]

    def _validate_dim(self, vecs: list[list[float]]) -> None:
        if not vecs:
            return
        got = len(vecs[0])
        if got != self.dim:
            # Auto-adjust dim if provider returns different size but allow with warning for migration
            logger.warning("Embedding dim mismatch: configured %s but provider returned %s", self.dim, got)
            # Do not raise immediately; let caller decide. For strict mode, uncomment:
            # raise VectorDimMismatchError(f"Expected dim {self.dim} got {got}")


_embedding_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = EmbeddingProvider()
    return _embedding_provider
