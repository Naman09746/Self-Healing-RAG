# Project Structure — Self-Healing RAG Pipeline

## Top-Level Layout

```
self-healing-rag-agent/
├── backend/                 # Python backend (FastAPI + LangGraph)
├── docs/                    # Architecture & design documentation
│   ├── archive/             # Archived legacy files (e.g. frontend-old.zip)
│   ├── plans/               # Roadmaps and implementation plans
│   └── visualizations/      # Interactive flowcharts and HTML graphs
├── frontend/                # Next.js frontend
├── infra/                   # Docker & Kubernetes deployment configs
├── scripts/                 # Utility and operational scripts
├── test_data/               # Sample documents for testing
├── chroma_data/             # ChromaDB vector store data (local dev fallback)
├── graphify-out/            # Knowledge graph export artifacts
├── scratch/                 # Scratch files for experiments
├── temp_uploads/            # Temporary file uploads
│
├── .env                     # Environment variables (local dev)
├── .env.example             # Environment variable template
├── .gitignore               # Git ignore rules
├── alembic.ini              # Alembic migration configuration
├── docker-compose.yml       # Local dev orchestration
├── Makefile                 # Build, test, deploy commands
├── pyproject.toml           # Python project config + dependencies
└── skills-lock.json         # Agent skill lockfile
```

---

## `backend/` — Python Backend

```
backend/
├── __init__.py
│
├── agents/                  # LangGraph agent implementations
│   ├── __init__.py
│   ├── critic/              # Phase 5: Claim extraction + grounding
│   │   ├── __init__.py
│   │   ├── agent.py         # Critic agent orchestration
│   │   ├── claim_extractor.py  # Extracts claims from LLM output
│   │   ├── grounding_verifier.py  # Verifies claims against context
│   │   └── verdict.py       # Grounding verdict data models
│   │
│   ├── evaluation/          # Phase 5: Evaluation framework
│   │   ├── __init__.py
│   │   └── agent.py         # Evaluation agent
│   │
│   ├── generation/          # Phase 4: LLM answer generation
│   │   ├── __init__.py
│   │   ├── agent.py         # Generation agent
│   │   └── llm_client.py    # Ollama API client
│   │
│   ├── healer/              # Phase 6: Self-healing
│   │   ├── __init__.py
│   │   └── query_rewriter.py  # Query rewriting for re-retrieval
│   │
│   ├── memory/              # Phase 4d: Memory & session management
│   │   └── agent.py         # Memory agent
│   │
│   ├── planner/             # Phase 2: Query complexity classification
│   │   └── agent.py         # Planner agent
│   │
│   ├── retrieval/           # Phase 3: Multi-modal retrieval
│   │   └── __init__.py
│   │
│   └── summarizer/          # Phase 4: Summarization
│       └── agent.py         # Summarizer agent
│
├── alembic/                 # Database migration management
│   ├── __init__.py
│   ├── env.py               # Alembic environment config
│   ├── script.py.mako       # Migration template
│   └── versions/
│       └── 001_initial_schema.py  # Initial DB schema
│
├── api/                     # FastAPI application
│   ├── __init__.py
│   ├── main.py              # App entry point, router registration
│   ├── middleware/
│   │   ├── rate_limit.py    # Redis-based rate limiting
│   │   └── request_id.py    # X-Request-ID header middleware
│   └── routers/
│       ├── __init__.py
│       ├── auth.py          # Authentication endpoints
│       └── ingest.py        # Document ingestion endpoints
│
├── core/                    # Core configuration & utilities
│   ├── __init__.py
│   ├── config.py            # App settings (pydantic-settings)
│   ├── logging.py           # Structured logging configuration
│   ├── observability.py     # OpenTelemetry tracing
│   ├── security.py          # JWT, password hashing, RBAC
│   └── telemetry.py         # Telemetry event collector
│
├── evaluation/              # Phase 5: Evaluation framework
│   ├── __init__.py
│   ├── benchmark.py         # Benchmark dataset loading & processing
│   ├── evaluator.py         # RAGAS-based metric computation
│   ├── queue.py             # Redis-backed evaluation job queue
│   ├── pipeline.py          # Offline evaluation pipeline
│   └── models.py            # Pydantic models for eval data
│
├── graph/                   # LangGraph pipeline orchestration
│   ├── __init__.py
│   ├── bounded_list.py      # Bounded list utility
│   ├── complexity.py        # Complexity classification logic
│   ├── container.py         # Dependency injection container
│   ├── edges.py             # Conditional edge logic
│   ├── nodes.py             # Graph node functions
│   ├── runner.py            # Graph execution runner
│   ├── state.py             # Graph state definition (TypedDict)
│   ├── stream_runner.py     # Streaming runner for WebSocket
│   └── workflow.py          # LangGraph workflow builder
│
├── ingestion/               # Document ingestion pipeline
│   ├── __init__.py
│   ├── chunker.py           # Document chunking logic
│   ├── pipeline.py          # Ingestion pipeline orchestration
│   └── loaders/             # File loaders (PDF, TXT, MD)
│
├── memory/                  # Memory & caching layer
│   ├── __init__.py
│   ├── query_cache.py       # Semantic query cache
│   └── session.py           # Session state management
│
├── storage/                 # Storage abstraction layer
│   ├── __init__.py
│   ├── reranker.py          # Cross-encoder reranking
│   ├── retriever.py         # Unified retriever (dense+sparse+graph)
│   ├── tenant.py            # Tenant isolation
│   ├── db/                  # Database utilities
│   ├── graph/               # Neo4j graph store
│   ├── relational/          # PostgreSQL/SQLite relational
│   └── vector/              # ChromaDB vector store
│
└── tests/                   # Backend test suites
    ├── __init__.py
    ├── test_api_smoke.py    # Smoke test for API endpoints
    ├── e2e/                 # End-to-end tests
    │   └── test_evaluation_e2e.py  # E2E evaluation pipeline test
    ├── fixtures/            # Test fixtures & mock data
    ├── integration/         # Integration tests
    │   ├── test_evaluator.py      # Evaluator integration test
    │   └── test_evaluation_queue.py  # Queue integration test
    └── unit/                # Unit tests
        ├── test_evaluator.py      # Evaluator unit tests
        ├── test_evaluation_queue.py  # Queue unit tests
        └── test_evaluation_pipeline.py  # Pipeline unit tests
```

### Key Backend Files

| File | Purpose |
|------|---------|
| `backend/api/main.py` | FastAPI application entry point |
| `backend/core/config.py` | Environment-based configuration |
| `backend/core/security.py` | JWT creation/verification, password hashing, RBAC |
| `backend/graph/workflow.py` | LangGraph DAG definition (7 phases) |
| `backend/graph/state.py` | Typed state flowing through pipeline |
| `backend/graph/stream_runner.py` | WebSocket streaming execution |
| `backend/graph/complexity.py` | Query complexity classification |
| `backend/storage/retriever.py` | Multi-modal retriever orchestration |
| `backend/evaluation/evaluator.py` | RAGAS metric computation |
| `backend/evaluation/queue.py` | Redis-backed eval job queue |
| `backend/evaluation/pipeline.py` | Offline evaluation runner |

---

## `frontend/` — Next.js Frontend (Current)

```
frontend/
├── public/                  # Static assets
│   ├── file.svg
│   ├── globe.svg
│   ├── next.svg
│   ├── vercel.svg
│   └── window.svg
│
├── src/
│   ├── app/                 # Next.js App Router pages
│   │   ├── layout.tsx       # Root layout
│   │   ├── page.tsx         # Home/landing page
│   │   └── globals.css      # Global styles
│   └── components/          # Shared React components
│
├── .gitignore
├── AGENTS.md
├── CLAUDE.md
├── eslint.config.mjs
├── next.config.ts
├── package.json
├── package-lock.json
├── postcss.config.mjs
├── README.md
├── tsconfig.json
```

---

## `frontend-old/` — Vite + React Frontend (Legacy)

```
frontend-old/
├── public/
│   ├── favicon.svg
│   └── icons.svg
│
├── src/
│   ├── App.css
│   ├── App.tsx              # Main application component
│   ├── index.css            # Global styles
│   ├── main.tsx             # Entry point
│   ├── api/                 # API client modules
│   ├── assets/              # Images, icons, fonts
│   └── components/          # Reusable UI components
│
├── .gitignore
├── eslint.config.js
├── index.html
├── package.json
├── package-lock.json
├── README.md
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
└── vite.config.ts
```

---

## `tests/` — Top-Level Tests

```
tests/
└── unit/                    # Top-level unit tests
    └── ...                  # Additional test modules
```

---

## `scripts/` — Utility Scripts

```
scripts/
├── deploy.sh                # Deployment automation
├── generate_test_docs.py    # Generates test PDF documents
├── migrate_sqlite_to_postgres.py  # DB migration utility
└── run_eval.py              # CLI entry point for evaluation runs
```

---

## `infra/` — Infrastructure

```
infra/
├── docker/
│   └── Dockerfile.api       # API server Docker image
└── k8s/
    └── api.yaml             # Kubernetes deployment manifest
```

---

## `docs/` — Documentation

```
docs/
├── archive/                 # Archived legacy assets (e.g. frontend-old.zip)
├── plans/                   # Implementation plans & roadmaps
│   ├── IMPLEMENTATION_MASTER_PLAN.md # Implementation master details
│   ├── IMPLEMENTATION_ROADMAP.md     # Multi-phase implementation roadmap
│   ├── PHASE1_IMPLEMENTATION_PLAN.md # Phase 1 plan details
│   └── REMEDIATION_PLAN.md           # Remediation tracking and issues
├── visualizations/          # Interactive charts and graphs
│   └── WORKFLOW_VISUALIZATION.html   # Interactive workflow graph
│
├── API_SPECIFICATION.md      # API endpoint specification
├── APP_FLOW.md              # Application flow diagrams
├── Architecture_review.md   # Architecture review document
├── DATABASE_SCHEMA.md        # Database schema documentation
├── DESIGN_SYSTEM.md          # UI design system specification
├── PRD.md                   # Product Requirements Document
├── PROJECT_STRUCTURE.md      # This file — project structure map
├── SELF_HEALING_RAG_BLUEPRINT.md # System blueprint
├── TRD.md                   # Technical Requirements Document
└── WIREFRAMES.md             # UI wireframe descriptions
```

---

## `test_data/` — Sample Documents

```
test_data/
├── incident_post_mortem_cluster_zero.pdf
├── project_omega_spec.pdf
└── q4_strategic_intelligence.pdf
```

---

## Module Dependency Graph

```
api/main.py
  ├── api/routers/auth.py       → core/security.py, core/config.py
  ├── api/routers/ingest.py     → ingestion/pipeline.py, core/security.py
  ├── api/middleware/rate_limit.py → core/config.py
  ├── api/middleware/request_id.py
  │
  ├── graph/workflow.py         → graph/nodes.py, graph/edges.py
  │   ├── agents/planner/agent.py
  │   ├── agents/generation/agent.py  → agents/generation/llm_client.py
  │   ├── agents/critic/agent.py
  │   │   ├── agents/critic/claim_extractor.py
  │   │   └── agents/critic/grounding_verifier.py → agents/critic/verdict.py
  │   ├── agents/healer/query_rewriter.py
  │   ├── agents/memory/agent.py
  │   ├── retrieval/  → storage/retriever.py
  │   │   ├── storage/vector/   → ChromaDB
  │   │   ├── storage/          → BM25
  │   │   └── storage/graph/    → Neo4j
  │   └── storage/reranker.py
  │
  ├── graph/state.py            → pydantic/typing
  ├── graph/runner.py
  ├── graph/stream_runner.py
  ├── graph/complexity.py
  │
  ├── core/config.py            → pydantic-settings, python-dotenv
  ├── core/logging.py           → structlog
  ├── core/observability.py     → OpenTelemetry
  ├── core/security.py          → jose (JWT), passlib
  ├── core/telemetry.py
  │
  ├── memory/query_cache.py     → Redis
  ├── memory/session.py
  │
  ├── ingestion/pipeline.py
  │   ├── ingestion/chunker.py
  │   └── ingestion/loaders/
  │
  └── evaluation/
      ├── benchmark.py          → datasets (Hugging Face)
      ├── evaluator.py          → ragas.metrics
      ├── queue.py              → Redis
      ├── pipeline.py
      └── models.py
```

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Runtime** | Python 3.12 | Backend application |
| **Web framework** | FastAPI | REST API + WebSocket |
| **Orchestration** | LangGraph | Pipeline state machine |
| **LLM** | Ollama (mistral:7b) | Local LLM inference |
| **Vector store** | ChromaDB | Dense retrieval index |
| **Sparse index** | BM25 (rank-bm25) | Keyword retrieval |
| **Graph DB** | Neo4j | Entity relationship graph |
| **Primary DB** | PostgreSQL | Persistent relational data |
| **Cache/Queue** | Redis | Semantic cache + eval queue |
| **Auth** | RS256 JWT | Stateless authentication |
| **Password** | bcrypt (passlib) | Secure password hashing |
| **Validation** | Pydantic v2 | Request/response schemas |
| **Migration** | Alembic | Database schema migration |
| **Testing** | pytest | Unit, integration, E2E tests |
| **Evaluation** | RAGAS | Faithfulness, relevancy, precision |
| **Frontend (new)** | Next.js 14 (App Router) | Web UI |
| **Frontend (old)** | Vite + React 18 | Legacy UI |
| **Container** | Docker + Docker Compose | Local dev environment |
| **Orchestration** | Kubernetes (kind) | Production deployment |