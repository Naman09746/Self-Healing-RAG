from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, model_validator, AliasChoices
from typing import Any, Union


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # API Settings
    PROJECT_NAME: str = "Self-Healing RAG Pipeline"
    API_V1_STR: str = "/api/v1"

    # =========================================================================
    # Security — RS256 JWT (Phase 6)
    # =========================================================================
    # SECRET_KEY is deprecated; use JWT_PRIVATE_KEY / JWT_PUBLIC_KEY instead.
    # SECRET_KEY: str  (removed — no default, no fallback; app fails if unset)
    JWT_ALGORITHM: str = "RS256"  # Migrated from HS256 in Phase 6

    # Base64-encoded PEM RSA private key (for signing tokens).
    # Generate with:  openssl genrsa 2048 | base64
    # Or via make jwt-keys.
    JWT_PRIVATE_KEY: str = Field(
        default="",
        description="Base64-encoded RSA private key (PEM) for JWT signing. "
                    "Required for RS256. If empty, app will auto-generate a "
                    "keypair on startup (development only).",
    )
    # Base64-encoded PEM RSA public key (for verifying tokens).
    JWT_PUBLIC_KEY: str = Field(
        default="",
        description="Base64-encoded RSA public key (PEM) for JWT verification. "
                    "Required for RS256. If empty, derived from private key.",
    )

    # LLM Settings (supports Ollama and OpenAI-compatible providers like Groq/OpenRouter)
    LLM_PROVIDER: str = Field(
        default="ollama",
        description="LLM provider: 'ollama' or 'openai' (compatible with Groq, OpenRouter, OpenAI, vLLM)."
    )
    OPENAI_API_KEY: str = Field(
        default="",
        description="API key for OpenAI-compatible providers (e.g. Groq, OpenRouter, OpenAI)."
    )
    OPENAI_BASE_URL: str = Field(
        default="",
        description="Custom base URL for OpenAI-compatible API (e.g. https://api.groq.com/openai/v1)."
    )
    OLLAMA_HOST: str = Field(default="http://localhost:11434")
    MODEL_NAME: str = Field(
        default="llama3.2:1b",
        validation_alias=AliasChoices("MODEL_NAME", "LLM_MODEL"),
    )
    SMALL_MODEL_NAME: str = Field(
        default="llama3.2:1b",
        validation_alias=AliasChoices("SMALL_MODEL_NAME", "LLM_SMALL_MODEL"),
    )
    EMBEDDING_MODEL: str = Field(default="nomic-embed-text")
    EMBEDDING_PROVIDER: str = Field(
        default="auto",
        description="Embedding provider: 'auto' (detect from EMBEDDING_MODEL), 'ollama', 'openai' (OpenAI/Groq/OpenRouter), 'hf'/'sentence_transformers' (local HF Qwen/BGE/Jina/GTE). "
                    "Set 'hf' for Qwen3-Embedding/BGE-M3 local inference, 'ollama' for qwen3-embedding:0.6b via Ollama, 'openai' for API.",
    )
    EMBEDDING_DEVICE: str = Field(
        default="auto",
        description="Device for HF embeddings: 'auto' (cuda>mps>cpu), 'cpu', 'cuda', 'mps'. Ignored for Ollama/OpenAI.",
    )
    EMBEDDING_BATCH_SIZE: int = Field(default=32, description="Batch size for HF embeddings (chunks per encode call). 32 optimal for CPU, 64+ for GPU.")
    EMBEDDING_NORMALIZE: bool = Field(default=True, description="L2-normalize HF embeddings for cosine search (pgvector vector_cosine_ops). Must be true for pgvector.")
    EMBEDDING_TRUST_REMOTE_CODE: bool = Field(default=False, description="Allow HF remote code (required for some Qwen models that ship custom code).")
    EMBEDDING_QUERY_PREFIX: str = Field(
        default="",
        description="Optional instruction prefix prepended to queries for HF models. "
                    "Qwen3 example: 'Instruct: Given a web search query, retrieve relevant passages that answer the query\\nQuery: '. "
                    "BGE-M3: 'Represent this sentence for searching relevant passages: '. Leave empty for default.",
    )
    EMBEDDING_PASSAGE_PREFIX: str = Field(default="", description="Optional prefix for passages/documents (rarely needed, HF only).")
    EMBEDDING_FALLBACK_ENABLED: bool = Field(
        default=False,
        description="Enable deterministic hash embedding fallback if provider fails. Must be False in production to prevent DB poisoning.",
    )
    LLM_TIMEOUT: int = Field(default=60, description="Hard timeout for LLM calls in seconds.")

    # Vector Store Settings — Pluggable Provider
    VECTOR_STORE_PROVIDER: str = Field(
        default="pgvector",
        description="Vector store backend: 'pgvector' ($0 Free-Tier on PostgreSQL), 'qdrant', or 'pinecone'.",
    )
    VECTOR_STORE_DIM: int = Field(
        default=768,
        description="Embedding dimension for the vector store. Must match EMBEDDING_MODEL output (nomic-embed-text=768).",
    )
    PGVECTOR_EF_SEARCH: int = Field(
        default=40,
        description="HNSW ef_search parameter for pgvector queries (higher = more recall, slower).",
    )
    PGVECTOR_USE_HALFVEC: bool = Field(
        default=False,
        description="Use halfvec(half precision) instead of vector for 50% storage reduction and ~3x cosine speedup. Requires pgvector >=0.7 and Postgres 15+. Enable for 10k+ rows free-tier optimization. When enabled, embedding column type is halfvec(dim).",
    )
    PGVECTOR_FILTERED_INDEX_TENANT: str | None = Field(
        default=None,
        description="If set (e.g. 'default'), creates a filtered HNSW index WHERE tenant_id = 'value' for 10k+ rows per-tenant optimization. Otherwise uses generic HNSW. For multi-tenant with many tenants, leave None and use enable_seqscan tuning.",
    )
    PGVECTOR_ENABLE_SEQSCAN_OFF: bool = Field(
        default=False,
        description="If True, sets LOCAL enable_seqscan = off before vector queries to force HNSW index usage even with WHERE tenant_id filter. Useful for 10k+ rows where planner incorrectly chooses seq scan + sort. Default False because seq scan is faster for <1k rows.",
    )
    QDRANT_URL: str = Field(
        default="",
        description="Qdrant HTTP/gRPC URL (e.g. http://localhost:6333). Required when VECTOR_STORE_PROVIDER=qdrant.",
    )
    QDRANT_API_KEY: str = Field(
        default="",
        description="Qdrant API key if auth is enabled.",
    )
    QDRANT_COLLECTION_NAME: str = Field(
        default="rag_collection",
        description="Qdrant collection name. Tenant scoping is via payload filter.",
    )
    PINECONE_API_KEY: str = Field(
        default="",
        description="Pinecone API key. Required when VECTOR_STORE_PROVIDER=pinecone.",
    )
    PINECONE_INDEX_NAME: str = Field(
        default="rag-collection",
        description="Pinecone index name.",
    )
    PINECONE_CLOUD: str = Field(default="aws")
    PINECONE_REGION: str = Field(default="us-east-1")

    # Session Store Settings — Pluggable (free-tier: pg uses Postgres, no extra containers)
    SESSION_STORE_PROVIDER: str = Field(
        default="pg",
        description="Session store backend: 'redis', 'pg', or 'memory'. 'pg' reuses DATABASE_URL (free-tier default).",
    )
    SESSION_TTL: int = Field(default=3600, description="Session TTL in seconds.")
    SESSION_POOL_SIZE: int = Field(default=20, description="Redis connection pool size.")

    # Sparse Store Settings — Pluggable (free-tier: pg_tsvector uses Postgres)
    SPARSE_PROVIDER: str = Field(
        default="pg_tsvector",
        description="Sparse retrieval backend: 'bm25' (in-memory), 'pg_tsvector' (Postgres tsvector, free-tier), 'tantivy' (future).",
    )

    # Reranker Settings — Pluggable (free-tier: none saves 80MB)
    RERANKER_PROVIDER: str = Field(
        default="none",
        description="Reranker backend: 'none' (RRF only, free-tier), 'cross-encoder' (sentence-transformers), 'cohere' (API).",
    )
    RERANKER_MODEL: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        description="Cross-encoder model name when RERANKER_PROVIDER=cross-encoder.",
    )
    COHERE_API_KEY: str = Field(default="", description="Cohere API key when RERANKER_PROVIDER=cohere.")

    # Graph Store Settings — Pluggable (free-tier: memory, no Neo4j container)
    GRAPH_PROVIDER: str = Field(
        default="memory",
        description="Graph store backend: 'memory' (in-memory, free-tier), 'neo4j' (requires Neo4j service), 'pg' (Postgres adjacency).",
    )

    # Neo4j Graph Settings
    NEO4J_ENABLED: bool = Field(
        default=False,
        description="Enable Neo4j knowledge graph integration. Disabled by default in cloud free deployments."
    )
    NEO4J_URI: str = Field(default="bolt://localhost:7687")
    NEO4J_USER: str = Field(default="neo4j")
    NEO4J_PASSWORD: str = Field(default="password")

    # CORS Settings
    CORS_ORIGINS: Union[list[str], str] = Field(
        default=[
            "*",
            "https://self-healing-rag-omega.vercel.app",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        description="Allowed CORS origins for API requests."
    )


    # Redis Settings (supports host/port or single REDIS_URL connection string)
    REDIS_URL: str = Field(
        default="",
        description="Complete Redis URI (e.g. rediss://default:pwd@host:6379). Overrides REDIS_HOST/PORT if set."
    )
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_PASSWORD: str = Field(
        default="",
        description="Redis password. Leave empty if no auth is configured on the Redis instance.",
    )
    REDIS_USE_SSL: bool = Field(
        default=False,
        description="Enable TLS for Redis connections.",
    )

    # Database Settings
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://admin:password@localhost:5432/self_healing_rag"
    )

    # RAG Settings
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    MAX_RETRIES: int = 1
    RELEVANCE_THRESHOLD: float = Field(
        default=0.5,
        description="Master relevance threshold (backward compat). Used for vector distance (1-threshold) and as fallback for reranker. Prefer explicit thresholds below.",
    )
    GROUNDING_THRESHOLD: float = 0.5
    MAX_HISTORY_TURNS: int = 5
    RRF_DENSE_WEIGHT: float = 1.0
    RRF_SPARSE_WEIGHT: float = 1.0
    RRF_JACCARD_THRESHOLD: float = 0.85

    # Phase 3: Explicit calibrated thresholds — separate score spaces
    # Vector cosine distance: 0=identical, 1=orthogonal, 2=opposite. Lower is better.
    VECTOR_DISTANCE_THRESHOLD: float = Field(
        default=0.65,
        description="Max distance for dense vector hits to be considered relevant. "
                    "Default 0.65 = clamp(1-RELEVANCE_THRESHOLD, 0.65, 0.85). "
                    "Relevant after re-ingest: 0.22-0.41, Irrelevant: 0.83+ (gap 0.41).",
    )
    # Cross-encoder reranker logits: unbounded approx -5..10, higher is better. Default 0.5 is conservative for ms-marco.
    RERANKER_THRESHOLD: float = Field(
        default=0.5,
        description="Min rerank_score (cross-encoder) to be relevant. "
                    "RRF scores 0.016 are NOT compared to this.",
    )
    # RRF fallback when reranker disabled: ranks fused, 0.016 rank0, 0.008 approx rank5+
    RRF_THRESHOLD: float = Field(
        default=0.008,
        description="Min RRF score (1/(k+rank+1)) to be relevant when RERANKER_PROVIDER=none. "
                    "Any non-empty RRF is considered lexical/semantic overlap; threshold is low.",
    )
    # Sparse ts_rank 0..1, typically 0.05-0.6; 0.01 is low fallback for ILIKE
    SPARSE_SCORE_THRESHOLD: float = Field(
        default=0.01,
        description="Min ts_rank score for sparse hits when no vector distance available.",
    )

    # Embedding Hardening (Phase 0.3) — fail-closed in prod
    EMBEDDING_STRICT_DIM: bool = Field(default=True, description="If True, raise on embedding dim mismatch instead of warning.")
    GRAPH_EXTRACTION_ENABLED: bool = Field(default=False, description="If True, ingestion extracts graph entities via LLM. Disabled by default to avoid 8s ingest latency; enable for graph RAG.")

    # LangGraph Checkpointer
    LANGGRAPH_CHECKPOINT_URI: str = Field(
        default="",
        description="Postgres connection URI for LangGraph's PostgresCheckpointer. "
                    "Uses psycopg (sync) driver for checkpoint reads/writes. "
                    "If empty and a remote DATABASE_URL is set, automatically derives from DATABASE_URL.",
    )

    # Adaptive Retrieval (Phase 3C)
    COMPLEXITY_USE_LLM: bool = Field(
        default=False,
        description="Use LLM fallback for complexity classification instead of rule-based."
    )
    ADAPTIVE_K_SIMPLE: int = Field(default=3, description="k for simple queries (score < 0.3)")
    ADAPTIVE_K_MEDIUM: int = Field(default=5, description="k for medium queries (0.3 ≤ score < 0.7)")
    ADAPTIVE_K_COMPLEX: int = Field(default=10, description="k for complex queries (score ≥ 0.7)")
    ADAPTIVE_RERANK_COMPLEX_TOP: int = Field(
        default=6, description="top_k for reranker when k=10 (avoid quality dilution)"
    )

    # Multi-Query Retrieval
    MULTI_QUERY_ENABLED: bool = Field(
        default=False,
        description="Enable multi-query retrieval fan-out for complex queries.",
    )
    MULTI_QUERY_MAX_VARIANTS: int = Field(
        default=3,
        description="Maximum number of query variants to evaluate during multi-query retrieval.",
    )

    # Multi-Tenancy
    DEFAULT_TENANT_ID: str = "default"

    # Security Enforcement
    STORAGE_ENFORCE_TENANT: bool = Field(
        default=True,
        description="If True, all storage operations require a non-empty tenant_id. "
                    "Retrieval fails closed with an error when tenant_id is missing."
    )
    AUDIT_LOG_RETRIEVALS: bool = Field(
        default=True,
        description="If True, log all retrieval operations with tenant_id, query_hash, "
                    "and chunk_count for audit trail."
    )

    # =========================================================================
    # Rate Limiting (Phase 6)
    # =========================================================================
    RATE_LIMIT_DEFAULT: int = Field(
        default=60, description="Max requests per window (default endpoint)."
    )
    RATE_LIMIT_AUTH: int = Field(
        default=5, description="Max requests per window (auth endpoints)."
    )
    RATE_LIMIT_WINDOW: int = Field(
        default=60, description="Rate limit window in seconds."
    )
    RATE_LIMIT_FAIL_CLOSED: bool = Field(
        default=False,
        description="If True, reject requests when Redis is unavailable. "
                    "If False, allow requests (fallback open).",
    )

    # =========================================================================
    # Concurrency Control (Phase 6)
    # =========================================================================
    CONCURRENCY_MAX_GLOBAL: int = Field(
        default=50, description="Max concurrent requests across all users."
    )
    CONCURRENCY_MAX_PER_USER: int = Field(
        default=5, description="Max concurrent requests per user."
    )

    # =========================================================================
    # Prompt Injection Detection (Phase 6)
    # =========================================================================
    PROMPT_INJECTION_ENABLED: bool = Field(
        default=True,
        description="Enable prompt injection detection on user queries.",
    )
    PROMPT_INJECTION_THRESHOLD: float = Field(
        default=0.5,
        description="Minimum threat score to block a request (0.0–1.0).",
    )

    # =========================================================================
    # Audit Logging (Phase 6)
    # =========================================================================
    AUDIT_LOG_DIR: str = Field(
        default="audit_logs",
        description="Directory for audit log JSONL files.",
    )
    AUDIT_LOG_MAX_BYTES: int = Field(
        default=100 * 1024 * 1024,  # 100 MB
        description="Max size of a single audit log file before rotation.",
    )
    AUDIT_LOG_BACKUP_COUNT: int = Field(
        default=10,
        description="Number of rotated audit log files to retain.",
    )

    # Environment
    ENV: str = Field(default="development", description="Environment: development | production | test")

    # OpenTelemetry (Phase 4C)
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(
        default="",
        description="OTLP HTTP endpoint for exporting traces. "
                    "Example: http://localhost:4318. Leave empty to use console exporter."
    )
    OTEL_CONSOLE_EXPORT: bool = Field(
        default=False,
        description="If True, also export traces to console (useful for development). Production should be False to avoid log spam and latency."
    )
    OTEL_SERVICE_NAME: str = Field(
        default="self-healing-rag",
        description="Service name for OpenTelemetry resource attributes."
    )

    # LangSmith (Phase 4C)
    LANGSMITH_API_KEY: str = Field(
        default="",
        description="LangSmith API key for LLM-level observability. "
                    "Leave empty to disable LangSmith tracing."
    )
    LANGSMITH_PROJECT: str = Field(
        default="self-healing-rag",
        description="LangSmith project name for run grouping."
    )

    # Evaluation LLM (Phase 1 — separate from application LLM to support OpenRouter)
    EVALUATION_LLM: str = Field(
        default="",
        description="LLM model for RAGAS evaluation (faithfulness, relevancy, precision, recall). "
                    "If empty, falls back to MODEL_NAME, then 'gpt-4o-mini'. "
                    "Use an OpenRouter model like 'nvidia/nemotron-3-ultra-550b:free' when LLM_PROVIDER=openrouter.",
    )
    EVALUATION_BASE_URL: str = Field(
        default="",
        description="Base URL for evaluation LLM (OpenAI-compatible). "
                    "If empty, falls back to OPENAI_BASE_URL. "
                    "Set to https://openrouter.ai/api/v1 for OpenRouter.",
    )
    EVALUATION_EMBEDDING_MODEL: str = Field(
        default="",
        description="Embedding model for RAGAS evaluation. "
                    "If empty, falls back to EMBEDDING_MODEL.",
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_url(cls, v: Any) -> Any:
        if isinstance(v, str) and v.strip():
            s = v.strip()
            # Auto-heal Neon typo if user combined -pooler with .c- region (which breaks DNS)
            if "-pooler.c-" in s:
                s = s.replace("-pooler.c-", ".c-")
            if s.startswith("postgres://"):
                s = s.replace("postgres://", "postgresql+asyncpg://", 1)
            elif s.startswith("postgresql://") and not s.startswith("postgresql+"):
                s = s.replace("postgresql://", "postgresql+asyncpg://", 1)
            
            try:
                from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
                p = urlparse(s)
                if p.query:
                    qs = parse_qs(p.query)
                    if "sslmode" in qs:
                        mode = qs.pop("sslmode")[0]
                        qs["ssl"] = [mode]
                    qs.pop("channel_binding", None)
                    qs.pop("target_session_attrs", None)
                    new_query = urlencode(qs, doseq=True)
                    s = urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, p.fragment))
            except Exception:
                if "sslmode=" in s:
                    s = s.replace("sslmode=", "ssl=")

            return s
        return v

    @field_validator("LANGGRAPH_CHECKPOINT_URI", mode="before")
    @classmethod
    def assemble_checkpoint_uri(cls, v: Any) -> str:
        if isinstance(v, str) and v.strip():
            s = v.strip()
            if "-pooler.c-" in s:
                s = s.replace("-pooler.c-", ".c-")
            if s.startswith("postgresql+psycopg://"):
                return s.replace("postgresql+psycopg://", "postgresql://", 1)
            elif s.startswith("postgres://"):
                return s.replace("postgres://", "postgresql://", 1)
            return s
        return ""

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def assemble_redis_url(cls, v: Any) -> str:
        if isinstance(v, str) and v.strip():
            s = "".join(v.split())
            if s.startswith("redis://") and "upstash.io" in s:
                s = s.replace("redis://", "rediss://", 1)
            return s
        return ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            s = v.strip()
            if not s or s == "*":
                return ["*"]
            if s.startswith("[") and s.endswith("]"):
                try:
                    import json
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed]
                except Exception:
                    pass
            return [x.strip() for x in s.split(",") if x.strip()]
        if isinstance(v, list):
            return [str(x) for x in v]
        return ["*"]

    @model_validator(mode="after")
    def auto_align_embedding_dim(self) -> "Settings":
        """Auto-align VECTOR_STORE_DIM for known embedding models (OpenAI, Qwen3, BGE-M3, Jina, GTE).

        Without this, fresh installs with EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B but VECTOR_STORE_DIM=768
        would create vector(768) table then fail on first ingest (dim mismatch 768 vs 1024).
        """
        emb_model = (getattr(self, "EMBEDDING_MODEL", "") or "").lower()
        # Import dim registry lazily to avoid circular
        try:
            from backend.storage.vector.embeddings import MODEL_DIM_REGISTRY, _resolve_model_dim

            target = _resolve_model_dim(getattr(self, "EMBEDDING_MODEL", ""))
            if target and self.VECTOR_STORE_DIM == 768 and target != 768:
                # Only override default 768, never override explicit user dim
                # Check that default wasn't intentionally set: nomic keeps 768
                if "nomic" not in emb_model:
                    self.VECTOR_STORE_DIM = target
                    return self
        except Exception:
            pass
        # Legacy OpenAI fallback if registry import fails
        if (
            "text-embedding-3-small" in emb_model
            or "text-embedding-ada-002" in emb_model
            or ("openai" in emb_model and "768" not in emb_model)
        ):
            if self.VECTOR_STORE_DIM == 768:
                self.VECTOR_STORE_DIM = 1536
        elif "text-embedding-3-large" in emb_model:
            if self.VECTOR_STORE_DIM == 768:
                self.VECTOR_STORE_DIM = 3072
        return self


    def with_overrides(self, **kwargs: Any) -> "Settings":
        """Return a copy of Settings with specified fields overridden without mutating global settings."""
        return self.model_copy(update=kwargs)

    def validate_deployment(self) -> list[str]:
        """Return list of blocking issues for production deployment (empty = ready)."""
        issues: list[str] = []
        # Vector dim vs embedding model parity — prevents 0-result fast-fail
        emb = (self.EMBEDDING_MODEL or "").lower()
        dim = self.VECTOR_STORE_DIM
        try:
            from backend.storage.vector.embeddings import _resolve_model_dim

            expected = _resolve_model_dim(self.EMBEDDING_MODEL or "")
            if expected and dim != expected:
                issues.append(f"VECTOR_STORE_DIM={dim} but EMBEDDING_MODEL={self.EMBEDDING_MODEL} requires {expected} — set VECTOR_STORE_DIM={expected} or run alembic upgrade (007)")
        except Exception:
            if "text-embedding-3-small" in emb and dim != 1536:
                issues.append(f"VECTOR_STORE_DIM={dim} but EMBEDDING_MODEL={self.EMBEDDING_MODEL} requires 1536 — set VECTOR_STORE_DIM=1536 or run migration 006")
            if "text-embedding-3-large" in emb and dim != 3072:
                issues.append(f"VECTOR_STORE_DIM={dim} but EMBEDDING_MODEL={self.EMBEDDING_MODEL} requires 3072")
            if "nomic-embed-text" in emb and dim not in (768,):
                issues.append(f"VECTOR_STORE_DIM={dim} mismatches nomic-embed-text (768)")
        # Prod secrets
        env = (self.ENV or "development").lower()
        if env == "production" and not self.JWT_PRIVATE_KEY:
            issues.append("ENV=production requires JWT_PRIVATE_KEY (base64 PEM) — generate with `python -c \"from backend.core.security import generate_rsa_keypair; print(generate_rsa_keypair())\"`")
        if self.EMBEDDING_FALLBACK_ENABLED and env == "production":
            issues.append("EMBEDDING_FALLBACK_ENABLED must be false in production (hash fallback poisons index)")
        # GRAPH_PROVIDER typo guard
        if getattr(self, "GRAPH_STORE_PROVIDER", None):
            issues.append("GRAPH_STORE_PROVIDER is deprecated typo — use GRAPH_PROVIDER")
        return issues


settings = Settings()