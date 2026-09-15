"""Embedding provider abstraction — decouples vector stores from Ollama/Chroma embedding_functions.

Supports 4 providers (auto-detected or via EMBEDDING_PROVIDER):
  - ollama:   local Ollama /api/embeddings (nomic-embed-text, qwen3-embedding:0.6b/8b, bge-m3, etc)
  - openai:   OpenAI-compatible API (OpenAI, Groq, OpenRouter)
  - hf:       local sentence-transformers (Qwen3-Embedding, BGE-M3, GTE-Qwen2, Jina-v3, etc)
  - hash:     deterministic SHA256 fallback (tests/offline only)

Powerful upgrades (2026 SOTA):
  - Qwen3-Embedding-0.6B (1024d, MTEB 64.9 multi, 600M) — best price/perf, beats text-embedding-3-large
  - Qwen3-Embedding-8B   (4096d, MTEB 70.3 SOTA) — for GPU hosts
  - BAAI/bge-m3           (1024d, dense+sparse+colbert, 8192 ctx) — versatile multilingual
  - BAAI/bge-large-en-v1.5 (1024d) — classic English strong
  - Alibaba-NLP/gte-Qwen2-1.5B-instruct (1536d) — instruction tuned

Usage:
  EMBEDDING_PROVIDER=hf
  EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B   # or BAAI/bge-m3, etc
  VECTOR_STORE_DIM=1024                        # must match model dim

  # Ollama variant (no extra deps):
  EMBEDDING_PROVIDER=ollama
  EMBEDDING_MODEL=qwen3-embedding:0.6b
  OLLAMA_HOST=http://localhost:11434
"""

from __future__ import annotations

import collections
import hashlib
import math
import unicodedata
from typing import Any

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Optional Redis query embedding cache (distributed, survives restarts)
# Uses REDIS_URL if set (Upstash). Falls back to in-memory LRU if Redis unavailable.
import json as _json

_redis_query_client = None


def _get_redis_query_cache():
    global _redis_query_client
    if _redis_query_client is not None:
        return _redis_query_client
    try:
        url = getattr(settings, "REDIS_URL", "") or ""
        if not url:
            # Only use Redis if REDIS_URL is explicitly set (avoids localhost probe in offline tests)
            return None
        import redis  # type: ignore

        client = redis.from_url(url, decode_responses=False, socket_timeout=0.5, socket_connect_timeout=0.5)
        # Quick ping with timeout
        client.ping()
        _redis_query_client = client
        logger.info("Redis query embedding cache enabled", url=url[:30] + "...")
        return client
    except Exception as e:
        logger.debug("Redis query cache not available", error=str(e))
        return None

try:
    import ollama  # type: ignore
except Exception:  # pragma: no cover
    ollama = None  # type: ignore

# ---------------------------------------------------------------------------
# Model dim registry — authoritative dims for known models (for auto-align + docs)
# ---------------------------------------------------------------------------
MODEL_DIM_REGISTRY: dict[str, int] = {
    # Ollama / local legacy
    "nomic-embed-text": 768,
    "all-minilm": 384,
    "mxbai-embed-large": 1024,
    # Ollama Qwen
    "qwen3-embedding:0.6b": 1024,
    "qwen3-embedding:0.6b-instruct": 1024,
    "qwen3-embedding:4b": 2560,
    "qwen3-embedding:8b": 4096,
    "qwen2.5-embedding": 1536,
    # HF Qwen3
    "qwen/qwen3-embedding-0.6b": 1024,
    "qwen/qwen3-embedding-4b": 2560,
    "qwen/qwen3-embedding-8b": 4096,
    "alibaba-nlp/gte-qwen2-1.5b-instruct": 1536,
    "alibaba-nlp/gte-qwen2-7b-instruct": 3584,
    # BGE family
    "baa/bge-m3": 1024,
    "baai/bge-m3": 1024,
    "baai/bge-large-en-v1.5": 1024,
    "baai/bge-base-en-v1.5": 768,
    "baai/bge-small-en-v1.5": 384,
    # Jina
    "jinaai/jina-embeddings-v3": 1024,
    "jinaai/jina-embeddings-v2-base-en": 768,
    # OpenAI
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "openai/text-embedding-3-small": 1536,
    "openai/text-embedding-3-large": 3072,
    # Cohere
    "embed-english-v3.0": 1024,
    "embed-multilingual-v3.0": 1024,
    # Voyage
    "voyage-3": 1024,
    "voyage-3-large": 1024,
}

# Global HF model cache (model_name -> SentenceTransformer instance)
_HF_MODEL_CACHE: dict[str, Any] = {}


def _resolve_model_dim(model: str) -> int | None:
    key = (model or "").strip().lower()
    # exact
    if key in MODEL_DIM_REGISTRY:
        return MODEL_DIM_REGISTRY[key]
    # try substring match for hf with org prefix
    for k, v in MODEL_DIM_REGISTRY.items():
        if k in key or key in k:
            return v
    return None


def _is_hf_model(model: str) -> bool:
    m = (model or "").lower().strip()
    # Ollama tags like "qwen3-embedding:0.6b" / "nomic-embed-text" have no '/' — never HF in auto mode
    if "/" not in m:
        return False
    if m.startswith("openai/"):
        return False
    # All HF repos contain '/' — check against known HF families
    hf_markers = ("qwen3-embedding", "qwen/qwen3", "bge-m3", "bge-large", "bge-base", "bge-small", "gte-qwen", "jina-embeddings", "e5-mistral", "instructor", "jinaai/", "baai/", "qwen/", "alibaba-nlp/")
    if any(tag in m for tag in hf_markers):
        return True
    # Also treat any '/' model that is in registry as HF (e.g., BAAI/bge-m3 exact)
    return m in MODEL_DIM_REGISTRY


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


_OPENAI_CLIENT_CACHE: dict[tuple[str, str], Any] = {}


def _get_openai_client(api_key: str, base_url: str | None) -> Any:
    """Reuse OpenAI client per (api_key prefix, base_url) to avoid TCP/TLS churn."""
    key = (api_key[:12] if api_key else "", base_url or "")
    if key in _OPENAI_CLIENT_CACHE:
        return _OPENAI_CLIENT_CACHE[key]
    try:
        from openai import OpenAI
    except Exception as e:
        raise EmbeddingError(f"openai package required for OPENAI embeddings: {e}") from e
    kwargs: dict[str, Any] = {}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(api_key=api_key, **kwargs)
    _OPENAI_CLIENT_CACHE[key] = client
    return client


def _openai_embed(texts: list[str], model: str, api_key: str, base_url: str | None) -> list[list[float]]:
    """Call OpenAI-compatible embeddings API with batching and character limits."""
    client = _get_openai_client(api_key, base_url)
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


def _hf_embed(
    texts: list[str],
    model: str,
    batch_size: int | None = None,
    normalize: bool | None = None,
    device: str | None = None,
    trust_remote_code: bool = False,
    query_prefix: str | None = None,
    passage_prefix: str | None = None,
    is_query: bool = False,
) -> list[list[float]]:
    """Local HF sentence-transformers embedding (Qwen3, BGE-M3, Jina, GTE).

    Lazy-loads and caches the SentenceTransformer. Supports:
      - batch encoding with configurable batch_size
      - L2 normalization (required for cosine in pgvector/Qdrant)
      - instruction prefixes (Qwen3 / BGE-M3 benefit from query instruction)
      - device auto-selection (cpu/cuda/mps)

    For Qwen3-Embedding, recommended prefixes:
      query_prefix="Instruct: Given a web search query, retrieve relevant passages that answer the query"
      passage_prefix="" (no prefix for documents)

    For BGE-M3, no prefix needed but query can use "Represent this sentence for searching relevant passages: "
    """
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as e:
        raise EmbeddingError(f"sentence-transformers required for HF embeddings (model={model}): {e}") from e

    # Resolve device
    if not device or device == "auto":
        try:
            import torch

            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        except Exception:
            device = "cpu"

    batch_size = batch_size or int(getattr(settings, "EMBEDDING_BATCH_SIZE", 32) or 32)
    if normalize is None:
        normalize = bool(getattr(settings, "EMBEDDING_NORMALIZE", True))
    if not trust_remote_code:
        trust_remote_code = bool(getattr(settings, "EMBEDDING_TRUST_REMOTE_CODE", False))

    # Load or reuse cached model
    cache_key = f"{model}::{device}::{trust_remote_code}"
    st_model = _HF_MODEL_CACHE.get(cache_key)
    if st_model is None:
        logger.info("Loading HF embedding model", model=model, device=device, normalize=normalize)
        try:
            st_model = SentenceTransformer(
                model,
                device=device,
                trust_remote_code=trust_remote_code,
            )
            _HF_MODEL_CACHE[cache_key] = st_model
            logger.info("HF model loaded", model=model, dim=st_model.get_sentence_embedding_dimension())
        except Exception as e:
            raise EmbeddingError(f"Failed to load HF model {model}: {e}") from e

    # Apply instruction prefixes if configured
    prefix = ""
    if is_query and query_prefix:
        prefix = query_prefix
    elif not is_query and passage_prefix:
        prefix = passage_prefix

    if prefix:
        texts = [f"{prefix}{t}" for t in texts]

    cleaned = [unicodedata.normalize("NFKC", t.strip()) or " " for t in texts]

    # SentenceTransformer.encode handles batching internally; we also chunk for large inputs
    # to avoid OOM on long doc lists (e.g., 2000 chunks)
    all_vecs: list[list[float]] = []
    for i in range(0, len(cleaned), batch_size):
        batch = cleaned[i : i + batch_size]
        vecs = st_model.encode(
            batch,
            batch_size=len(batch),
            normalize_embeddings=normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        # vecs is ndarray (batch, dim)
        for v in vecs:
            all_vecs.append([float(x) for x in v])
    return all_vecs


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


def clear_hf_cache() -> None:
    """Clear cached HF models (useful in tests or after config change)."""
    _HF_MODEL_CACHE.clear()


class EmbeddingProvider:
    """Unified embedding provider used by all vector stores."""

    def __init__(
        self,
        model: str | None = None,
        dim: int | None = None,
        use_hash_fallback: bool | None = None,
    ) -> None:
        self.model = model or getattr(settings, "EMBEDDING_MODEL", "nomic-embed-text")
        # Auto-infer dim from registry if not explicitly set and VECTOR_STORE_DIM is still default 768
        inferred = _resolve_model_dim(self.model)
        cfg_dim = dim or getattr(settings, "VECTOR_STORE_DIM", 768)
        # If cfg is default 768 but model implies different, auto-align (helps fresh installs)
        if inferred and cfg_dim == 768 and inferred != 768:
            # Only auto-align if settings hasn't been intentionally pinned; allow explicit override
            # Check if EMBEDDING_MODEL was default nomic — then keep 768
            if "nomic" not in (self.model or "").lower():
                cfg_dim = inferred
                logger.info("Auto-aligned VECTOR_STORE_DIM to model", model=self.model, dim=cfg_dim)
        self.dim = cfg_dim
        # Respect global flag if not explicitly overridden (tests can pass True)
        if use_hash_fallback is None:
            use_hash_fallback = bool(getattr(settings, "EMBEDDING_FALLBACK_ENABLED", True))
            # Default True for offline/tests; prod should set False via .env
            # If no setting, fallback to True to keep backward compat with existing tests
            if not hasattr(settings, "EMBEDDING_FALLBACK_ENABLED"):
                use_hash_fallback = True
        self.use_hash_fallback = use_hash_fallback
        self._provider = (getattr(settings, "LLM_PROVIDER", "ollama") or "ollama").lower()
        self._embedding_provider = (getattr(settings, "EMBEDDING_PROVIDER", "auto") or "auto").lower().strip()
        self._ollama_host = getattr(settings, "OLLAMA_HOST", "http://localhost:11434")
        self._openai_key = getattr(settings, "OPENAI_API_KEY", "") or ""
        self._openai_url = getattr(settings, "OPENAI_BASE_URL", "") or None
        # HF specific
        self._hf_device = getattr(settings, "EMBEDDING_DEVICE", "auto") or "auto"
        self._hf_batch = int(getattr(settings, "EMBEDDING_BATCH_SIZE", 32) or 32)
        self._hf_normalize = bool(getattr(settings, "EMBEDDING_NORMALIZE", True))
        self._hf_trust = bool(getattr(settings, "EMBEDDING_TRUST_REMOTE_CODE", False))
        self._hf_query_prefix = getattr(settings, "EMBEDDING_QUERY_PREFIX", "") or ""
        self._hf_passage_prefix = getattr(settings, "EMBEDDING_PASSAGE_PREFIX", "") or ""
        # Bounded in-memory LRU query cache (keyed by provider, model, normalized query)
        self._query_cache: collections.OrderedDict[tuple[str, str, str], list[float]] = collections.OrderedDict()
        self._query_cache_maxsize = 1024
        self._last_used_hash_fallback = False

    def _should_use_hf(self) -> bool:
        if self._embedding_provider in ("hf", "sentence_transformers", "sentence-transformers", "local"):
            return True
        if self._embedding_provider == "auto" and _is_hf_model(self.model):
            return True
        return False

    def _should_use_openai(self) -> bool:
        if self._embedding_provider in ("openai", "groq", "openrouter"):
            return bool(self._openai_key)
        # auto: use openai if key present and provider is openai-like OR model is openai
        if self._openai_key and (self._provider in ("openai", "groq", "openrouter") or "text-embedding" in (self.model or "").lower() or "openai/" in (self.model or "").lower()):
            return True
        return False

    def _should_use_ollama(self) -> bool:
        if self._embedding_provider == "ollama":
            return True
        if self._embedding_provider == "auto":
            # if not hf and not openai, try ollama
            return True
        return False

    def embed(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        if not texts:
            return []
        self._last_used_hash_fallback = False

        # 1) HF local (Qwen3, BGE-M3, etc) — highest quality for self-hosted, no API cost
        if self._should_use_hf():
            try:
                vecs = _hf_embed(
                    texts,
                    self.model,
                    batch_size=self._hf_batch,
                    normalize=self._hf_normalize,
                    device=self._hf_device,
                    trust_remote_code=self._hf_trust,
                    query_prefix=self._hf_query_prefix or None,
                    passage_prefix=self._hf_passage_prefix or None,
                    is_query=is_query,
                )
                self._validate_dim(vecs)
                return vecs
            except Exception as e:
                logger.warning("HF embeddings failed, trying next provider", error=str(e), model=self.model)
                if not self.use_hash_fallback and self._embedding_provider in ("hf", "sentence_transformers", "local"):
                    raise

        # 2) OpenAI-compatible (OpenAI, Groq, OpenRouter) — good for free-tier Neon prod
        if self._should_use_openai():
            try:
                vecs = _openai_embed(texts, self.model, self._openai_key, self._openai_url)
                self._validate_dim(vecs)
                return vecs
            except Exception as e:
                logger.warning("OpenAI embeddings failed, falling back", error=str(e))
                if not self.use_hash_fallback and self._embedding_provider in ("openai", "groq", "openrouter"):
                    raise

        # 3) Ollama (nomic, qwen3-embedding:0.6b, bge-m3 via ollama, etc)
        if self._should_use_ollama():
            try:
                if ollama is not None:
                    vecs = _ollama_embed(texts, self.model, self._ollama_host)
                    self._validate_dim(vecs)
                    return vecs
            except Exception as e:
                logger.warning("Ollama embeddings failed, falling back to hash", error=str(e))
                if not self.use_hash_fallback and self._embedding_provider == "ollama":
                    raise

        if self.use_hash_fallback:
            self._last_used_hash_fallback = True
            logger.warning("Using deterministic hash embeddings (offline/test mode)", dim=self.dim, count=len(texts))
            return _hash_embed(texts, self.dim)
        raise EmbeddingError("No embedding provider available and hash fallback disabled")

    def embed_query(self, text: str) -> list[float]:
        norm_text = unicodedata.normalize("NFKC", text.strip()) if text else ""
        # Distinguish query vs passage in cache key (HF instruction prefixes matter)
        cache_key = (self._embedding_provider or self._provider, self.model, norm_text)
        if cache_key in self._query_cache:
            self._query_cache.move_to_end(cache_key)
            return self._query_cache[cache_key]

        # Try Redis distributed cache (if REDIS_URL set) — 5ms timeout
        redis_client = None
        redis_key = None
        if not self._last_used_hash_fallback:
            try:
                redis_client = _get_redis_query_cache()
                if redis_client is not None:
                    # Key includes model to avoid cross-model pollution
                    import hashlib as _hl

                    h = _hl.sha256(f"{self.model}::{norm_text}".encode("utf-8")).hexdigest()[:32]
                    redis_key = f"emb:q:{h}"
                    cached = redis_client.get(redis_key)
                    if cached:
                        try:
                            vec = _json.loads(cached)  # type: ignore
                            if isinstance(vec, list) and len(vec) == self.dim:
                                # Promote to in-memory LRU
                                if len(self._query_cache) >= self._query_cache_maxsize:
                                    self._query_cache.popitem(last=False)
                                self._query_cache[cache_key] = vec
                                return vec
                        except Exception:
                            pass
            except Exception:
                redis_client = None
                redis_key = None

        # For HF models, apply query prefix
        if self._should_use_hf():
            vecs = self.embed([text], is_query=True)
            vec = vecs[0]
        else:
            vec = self.embed([text])[0]
        # Never cache hash fallback embeddings to prevent polluting production cache
        if not self._last_used_hash_fallback:
            if len(self._query_cache) >= self._query_cache_maxsize:
                self._query_cache.popitem(last=False)
            self._query_cache[cache_key] = vec
            # Also store in Redis with TTL 24h
            if redis_client is not None and redis_key is not None:
                try:
                    redis_client.setex(redis_key, 86400, _json.dumps(vec))
                except Exception:
                    pass
        return vec

    def _validate_dim(self, vecs: list[list[float]]) -> None:
        if not vecs:
            return
        got = len(vecs[0])
        if got != self.dim:
            # Auto-sync any dim mismatch (generalized from 768->1536/3072 to any)
            # Common transitions: 768->1024 (Qwen0.6/BGE-M3), 768->4096 (Qwen8B), 1536->1024, etc.
            # If EMBEDDING_STRICT_DIM is False, just warn; if True, auto-sync and log
            expected = _resolve_model_dim(self.model)
            if expected and got == expected:
                logger.info("Auto-syncing embedding provider dimension to model registry", old_dim=self.dim, new_dim=got, model=self.model)
                self.dim = got
                return
            # Fallback heuristic: allow any auto-sync when STRICT is enabled but dim clearly mismatched
            # (pgvector store will ALTER TABLE; better than failing closed on prod)
            if got in (384, 768, 1024, 1536, 2560, 3072, 3584, 4096):
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
