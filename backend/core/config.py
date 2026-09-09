from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
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
    MODEL_NAME: str = Field(default="llama3.2:1b")
    SMALL_MODEL_NAME: str = Field(default="llama3.2:1b")
    EMBEDDING_MODEL: str = Field(default="nomic-embed-text")
    LLM_TIMEOUT: int = Field(default=30, description="Hard timeout for LLM calls in seconds.")

    # Vector Store Settings
    CHROMA_HOST: str = Field(default="localhost")
    CHROMA_PORT: int = Field(default=8000)
    CHROMA_COLLECTION_NAME: str = Field(default="rag_collection")
    CHROMA_ALLOW_RESET: bool = Field(
        default=False,
        description="Allow ChromaDB reset API. Set to true only in development."
    )
    CHROMA_USE_LOCAL: bool = Field(
        default=True,
        description="Use local embedded ChromaDB storage without attempting network connection to localhost:8000."
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
    RELEVANCE_THRESHOLD: float = 0.5
    GROUNDING_THRESHOLD: float = 0.5
    MAX_HISTORY_TURNS: int = 5

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

    # OpenTelemetry (Phase 4C)
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(
        default="",
        description="OTLP HTTP endpoint for exporting traces. "
                    "Example: http://localhost:4318. Leave empty to use console exporter."
    )
    OTEL_CONSOLE_EXPORT: bool = Field(
        default=True,
        description="If True, also export traces to console (useful for development)."
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

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_url(cls, v: Any) -> str:
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


    def with_overrides(self, **kwargs) -> "Settings":
        """Return a copy of Settings with specified fields overridden without mutating global settings."""
        return self.model_copy(update=kwargs)

settings = Settings()