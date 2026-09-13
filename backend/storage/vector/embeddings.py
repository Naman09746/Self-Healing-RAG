"""Embedding provider abstraction — decouples vector stores from Ollama/Chroma embedding_functions."""

from __future__ import annotations

import collections
import hashlib
import math
import unicodedata
from typing import Any

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
        clean_text = unicodedata.normalize("NFKC", t.strip()) or " "
        resp = client.embeddings(model=model, prompt=clean_text)
        vec = resp.get("embedding")
        if vec is None:
            # fallback for newer client where key is 'embeddings'
            vec = resp.get("embeddings") or resp.get("data")
        if vec is None:
            raise EmbeddingError(f"Ollama embeddings returned no vector for text prefix: {clean_text[:60]}")
        # ollama can return nested list
        if isinstance(vec[0], list):
            vec = vec[0]
        vectors.append([float(x) for x in vec])
    return vectors


def _openai_embed(texts: list[str], model: str, api_key: str, base_url: str | None) -> list[list[float]]:
    """Call OpenAI-compatible embeddings API with batching and character limits."""
    try:
        from openai import OpenAI
    except Exception as e:
        raise EmbeddingError(f"openai package required for OPENAI embeddings: {e}") from e
    kwargs: dict[str, Any] = {}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(api_key=api_key, **kwargs)
    embed_model = model or "text-embedding-3-small"
    if any(tag in embed_model.lower() for tag in ("nomic", "ollama", "llama", "bge", "all-minilm")):
        embed_model = "text-embedding-3-small"
        
    # OpenRouter requires explicit provider prefixes
    if base_url and "openrouter.ai" in base_url.lower():
        if embed_model == "text-embedding-3-small":
            embed_model = "openai/text-embedding-3-small"
        elif embed_model == "text-embedding-3-large":
            embed_model = "openai/text-embedding-3-large"

    # Batching to avoid OpenAI request token/size limits (max 64 items or ~24k chars per batch)
    all_vectors: list[list[float]] = []
    current_batch: list[str] = []
    current_chars = 0
    max_batch_size = 64
    max_batch_chars = 24000

    def _flush_batch(batch: list[str]) -> list[list[float]]:
        if not batch:
            return []
        cleaned = [unicodedata.normalize("NFKC", t.strip()) or " " for t in batch]
        resp = client.embeddings.create(model=embed_model, input=cleaned)
        return [list(d.embedding) for d in resp.data]

    for t in texts:
        t_len = len(t)
        if current_batch and (len(current_batch) >= max_batch_size or current_chars + t_len > max_batch_chars):
            all_vectors.extend(_flush_batch(current_batch))
            current_batch = [t]
            current_chars = t_len
        else:
            current_batch.append(t)
            current_chars += t_len

    if current_batch:
        all_vectors.extend(_flush_batch(current_batch))

    return all_vectors


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
        use_hash_fallback: bool | None = None,
    ) -> None:
        self.model = model or getattr(settings, "EMBEDDING_MODEL", "nomic-embed-text")
        self.dim = dim or getattr(settings, "VECTOR_STORE_DIM", 768)
        # Respect global flag if not explicitly overridden (tests can pass True)
        if use_hash_fallback is None:
            use_hash_fallback = bool(getattr(settings, "EMBEDDING_FALLBACK_ENABLED", True))
            # Default True for offline/tests; prod should set False via .env
            # If no setting, fallback to True to keep backward compat with existing tests
            if not hasattr(settings, "EMBEDDING_FALLBACK_ENABLED"):
                use_hash_fallback = True
        self.use_hash_fallback = use_hash_fallback
        self._provider = (getattr(settings, "LLM_PROVIDER", "ollama") or "ollama").lower()
        self._ollama_host = getattr(settings, "OLLAMA_HOST", "http://localhost:11434")
        self._openai_key = getattr(settings, "OPENAI_API_KEY", "") or ""
        self._openai_url = getattr(settings, "OPENAI_BASE_URL", "") or None
        # Bounded in-memory LRU query cache (keyed by provider, model, normalized query)
        self._query_cache: collections.OrderedDict[tuple[str, str, str], list[float]] = collections.OrderedDict()
        self._query_cache_maxsize = 1024
        self._last_used_hash_fallback = False

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._last_used_hash_fallback = False
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
            self._last_used_hash_fallback = True
            logger.warning("Using deterministic hash embeddings (offline/test mode)", dim=self.dim, count=len(texts))
            return _hash_embed(texts, self.dim)
        raise EmbeddingError("No embedding provider available and hash fallback disabled")

    def embed_query(self, text: str) -> list[float]:
        norm_text = unicodedata.normalize("NFKC", text.strip()) if text else ""
        cache_key = (self._provider, self.model, norm_text)
        if cache_key in self._query_cache:
            self._query_cache.move_to_end(cache_key)
            return self._query_cache[cache_key]

        vec = self.embed([text])[0]
        # Never cache hash fallback embeddings to prevent polluting production cache
        if not self._last_used_hash_fallback:
            if len(self._query_cache) >= self._query_cache_maxsize:
                self._query_cache.popitem(last=False)
            self._query_cache[cache_key] = vec
        return vec

    def _validate_dim(self, vecs: list[list[float]]) -> None:
        if not vecs:
            return
        got = len(vecs[0])
        if got != self.dim:
            if self.dim == 768 and got in (1536, 3072):
                logger.info("Auto-syncing embedding provider dimension", old_dim=self.dim, new_dim=got)
                self.dim = got
                return
            msg = f"Embedding dim mismatch: configured {self.dim} but provider returned {got} for model {self.model}"
            if getattr(settings, "EMBEDDING_STRICT_DIM", True):
                logger.error(msg)
                raise EmbeddingError(msg + ". Set VECTOR_STORE_DIM to match EMBEDDING_MODEL or disable EMBEDDING_STRICT_DIM.")
            logger.warning(msg + " (strict dim disabled, proceeding)")


_embedding_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = EmbeddingProvider()
    return _embedding_provider
