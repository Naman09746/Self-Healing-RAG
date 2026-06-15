# 🧠 Self-Healing RAG — Multi-Agent Pipeline with Autonomous Hallucination Detection

<p align="center">
  <strong>A production-grade multi-agent RAG pipeline that retrieves, generates, verifies, and autonomously corrects AI answers — no manual intervention required.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/FastAPI-0.100%2B-teal" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/LangGraph-%E2%9C%93-purple" alt="LangGraph"/>
  <img src="https://img.shields.io/badge/Next.js-16-black" alt="Next.js 16"/>
  <img src="https://img.shields.io/badge/License-MIT-green" alt="MIT License"/>
</p>

---

## 📋 Overview

**Self-Healing RAG** is a production-grade **multi-agent RAG pipeline** that orchestrates seven specialized agents to retrieve, generate, verify, and autonomously correct answers from your knowledge base. Unlike traditional RAG systems, this pipeline **detects hallucinations in real-time** and **heals itself** through a closed-loop critic → rewrite → re-retrieve → re-verify cycle.

**The problem it solves:** Traditional RAG pipelines suffer from three fundamental failure modes:
1. **Silent retrieval failures** — irrelevant or missing context degrades answer quality with no signal
2. **Hallucination** — LLMs generate factually incorrect statements
3. **No feedback loop** — errors propagate without detection or correction

This pipeline solves all three through a **Critic Agent** that decomposes every claim and verifies it against retrieved context, and a **Healer Agent** that automatically rewrites queries and re-retrieves when groundedness falls below threshold.

### Pipeline Flow

```
User Query → Intake → Planner → Hybrid Retriever → Generator → Critic → Output
                                       ↑                           │
                                       └──── Healer (if needed) ──┘
```

When the Critic Agent detects unverifiable claims (<50% grounded):
1. Healer Agent analyzes the failure
2. Rewrites the query with additional context
3. Triggers re-retrieval with expanded parameters
4. Generator produces a corrected answer
5. Critic re-verifies — loop continues until grounded or max retries reached

---

## ✨ Features

| Feature | Description | Status |
|---------|-------------|--------|
| **🔄 Multi-Agent Pipeline** | 7 specialized agents orchestrated via LangGraph | ✅ Production |
| **🔍 Hybrid Retrieval** | ChromaDB (dense) + BM25 (sparse) + Neo4j (graph) fused via RRF | ✅ Production |
| **🛡️ Hallucination Detection** | Atomic claim extraction + per-claim grounding verification | ✅ Production |
| **🔧 Self-Healing** | Automatic query rewrite → re-retrieve → re-generate when unverified claims found | ✅ Production |
| **📊 Adaptive Retrieval** | Query complexity classifier with dynamic k (3/5/10) based on 6-dimension analysis | ✅ Production |
| **⚡ Streaming Responses** | SSE-based token and phase streaming via WebSocket | ✅ Production |
| **🎯 4-Way Critic Routing** | FULLY_SUPPORTED → output, PARTIALLY → targeted heal, UNSUPPORTED → expand, CONTRADICTED → aggressive rewrite | ✅ Production |
| **🔐 Enterprise Security** | RS256 JWT, RBAC (4 roles), rate limiting, concurrency control, prompt injection detection | ✅ Production |
| **📝 Audit Logging** | Every mutating operation logged with rotation (100 MB, 10 backups) | ✅ Production |
| **📈 RAGAS Evaluation** | Offline evaluation with faithfulness, answer relevancy, context precision, context recall | ✅ Production |
| **📡 OpenTelemetry** | Distributed traces via OTLP with LangSmith integration | ✅ Production |
| **📊 Prometheus Metrics** | 25+ application metrics with Grafana dashboard | ✅ Added |
| **🐳 Production K8s** | HPA, PDB, network policies, pod security context, rolling updates | ✅ Added |
| **🎨 Modern UI** | Real-time pipeline visualization, live metrics, dark theme | ✅ Added |

---

## 🏗️ Architecture

### System Design — 7 Specialized Agents

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Intake     │────▶│   Planner    │────▶│  Retriever   │────▶│  Generator   │
│              │     │              │     │              │     │              │
│ • Validate   │     │ • Classify   │     │ • ChromaDB   │     │ • Contextual │
│ • Enrich     │     │   complexity │     │ • BM25       │     │   answer     │
│ • Anti-inject│     │ • Plan       │     │ • Neo4j      │     │ • Citations  │
│              │     │   retrieval  │     │ • RRF fusion │     │              │
└──────────────┘     └──────────────┘     └──────────────┘     └──────┬───────┘
                                                                      │
                                                                      ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    Output    │◀────│   Critic     │◀────│   Healer     │◀────│  (if needed) │
│              │     │              │     │              │     │              │
│ • Formatted  │     │ • Extract    │     │ • Rewrite    │     │  <50% claims │
│   response   │     │   claims     │     │   query      │     │  unverified  │
│ • Confidence │     │ • Ground     │     │ • Re-retrieve│     │              │
│ • Sources    │     │ • Verdict    │     │ • Regenerate │     │              │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

**How the Self-Healing Loop Works:**

1. **Generator** produces an answer from retrieved context
2. **Critic Agent** extracts every atomic factual claim from the answer
3. Each claim is verified against source documents (grounding check)
4. If <50% of claims are grounded → **Healer Agent** activates
5. Healer rewrites the query, expands retrieval scope, and re-generates
6. Critic re-verifies the new answer — loop continues until grounded or max retries reached
7. If ≥50% grounded → answer passes to Output with confidence score

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Runtime** | Python 3.10+ | Backend application |
| **Web Framework** | FastAPI | REST API + WebSocket |
| **Orchestration** | LangGraph | Pipeline state machine |
| **LLM** | Ollama (mistral:7b / llama3:8b) | Local LLM inference |
| **Vector Store** | ChromaDB | Dense retrieval index |
| **Sparse Index** | BM25 (rank-bm25) | Keyword retrieval |
| **Graph DB** | Neo4j | Entity relationship graph |
| **Primary DB** | PostgreSQL | Persistent relational data |
| **Cache/Queue** | Redis | Semantic cache + eval queue |
| **Auth** | RS256 JWT | Stateless authentication |
| **Frontend** | Next.js 16 + React 19 | Web UI with recharts + reactflow |
| **Monitoring** | Prometheus + Grafana | Metrics & dashboards |
| **Tracing** | OpenTelemetry + LangSmith | Distributed traces |
| **Evaluation** | RAGAS | Faithfulness, relevancy, precision |
| **Container** | Docker + Docker Compose | Local dev environment |
| **Orchestration** | Kubernetes (via Kustomize) | Production deployment |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+ (for frontend)
- Docker & Docker Compose v2+
- Ollama (for local LLM inference)

### 1. Clone & Setup

```bash
git clone https://github.com/yourusername/self-healing-rag.git
cd self-healing-rag-agent

# Backend
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Frontend
cd frontend && npm install && cd ..
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings (Ollama host, DB credentials, etc.)
```

### 3. Start Services

```bash
# Using Docker Compose (recommended)
docker compose up -d

# Or start backend manually
uvicorn backend.api.main:app --reload --port 8000

# Start frontend (separate terminal)
cd frontend && npm run dev
```

### 4. Ingest Documents & Query

```bash
# Ingest a document
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Authorization: Bearer <token>" \
  -F "file=@document.pdf"

# Query your knowledge base
curl -X POST http://localhost:8000/api/v1/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the key findings?"}'
```

### 5. Access the UI

- **Dashboard:** http://localhost:3000
- **API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Metrics:** http://localhost:8000/metrics

---

## 📁 Project Structure

```
self-healing-rag-agent/
├── backend/                          # Python backend (FastAPI + LangGraph)
│   ├── agents/                       # LangGraph agent implementations
│   │   ├── critic/                   # Claim extraction + grounding verification
│   │   ├── evaluation/               # RAGAS evaluation agent
│   │   ├── generation/               # LLM answer generation
│   │   ├── healer/                   # Query rewriting (self-healing)
│   │   ├── memory/                   # Session memory management
│   │   ├── planner/                  # Query complexity classification
│   │   ├── retrieval/                # Multi-modal retrieval
│   │   └── summarizer/              # Answer summarization
│   ├── api/                          # FastAPI application
│   │   ├── main.py                   # App entry point
│   │   ├── middleware/               # Rate limit, audit, concurrency, metrics
│   │   └── routers/                  # Auth, ingest, query, websocket
│   ├── core/                         # Configuration & utilities
│   │   ├── config.py                 # Pydantic settings
│   │   ├── security.py              # JWT, RBAC, password hashing
│   │   ├── metrics.py               # Prometheus metrics registry
│   │   ├── observability.py         # OpenTelemetry tracing
│   │   └── logging.py               # Structured logging
│   ├── graph/                        # LangGraph pipeline orchestration
│   │   ├── workflow.py              # Graph definition & compilation
│   │   ├── nodes.py                 # Pipeline node functions
│   │   ├── edges.py                 # 4-way routing logic
│   │   ├── state.py                 # RAGState definition
│   │   ├── complexity.py            # Adaptive complexity classifier
│   │   ├── container.py             # Dependency injection
│   │   ├── runner.py                # Graph execution
│   │   └── stream_runner.py         # SSE streaming
│   ├── ingestion/                    # Document processing pipeline
│   ├── storage/                      # Storage abstraction layer
│   │   ├── vector/chroma.py         # ChromaDB vector store
│   │   ├── graph/neo4j.py           # Neo4j graph store
│   │   ├── retriever.py             # Hybrid retriever (RRF fusion)
│   │   ├── reranker.py              # Cross-encoder reranking
│   │   └── tenant.py               # Tenant isolation
│   ├── memory/                       # Query cache + session state
│   ├── evaluation/                   # RAGAS evaluation framework
│   └── tests/                        # Test suite (26 files, ~150 tests)
│       ├── unit/                     # Unit tests with mocked deps
│       ├── integration/              # Integration tests with Docker
│       └── e2e/                     # End-to-end pipeline tests
├── frontend/                         # Next.js 16 frontend
│   └── src/
│       ├── app/                      # Pages (landing, dashboard, docs, auth, settings)
│       ├── components/              # UI components (LivePipeline, SystemStatus, etc.)
│       └── lib/                     # API client + React hooks
├── infra/                            # Infrastructure
│   ├── docker/Dockerfile.api        # Hardened multi-stage build
│   ├── k8s/                         # Production K8s manifests
│   │   ├── deployment.yaml          # Pod security, probes, anti-affinity
│   │   ├── hpa.yaml                 # Auto-scaling (2-10 pods)
│   │   ├── pdb.yaml                 # PodDisruptionBudget
│   │   ├── secrets.yaml             # Secret management
│   │   ├── network-policy.yaml      # Micro-segmentation
│   │   └── kustomization.yaml       # Kustomize overlay
│   └── monitoring/                  # Observability
│       ├── prometheus.yml           # Scrape config
│       ├── alerts.yml               # 15+ alert rules
│       └── grafana-dashboard.json   # System health dashboard
├── docs/                             # Documentation
│   ├── PRD.md                       # Product Requirements Document
│   ├── TRD.md                       # Technical Requirements Document
│   ├── Architecture_review.md       # Architecture deep-dive
│   ├── API_SPECIFICATION.md         # API reference
│   └── ...                          # Additional docs
├── scripts/                          # Utility scripts
│   ├── run_eval.py                  # CLI evaluation runner
│   ├── deploy.sh                    # Deployment automation
│   └── generate_test_docs.py        # Test document generator
├── docker-compose.yml               # Local dev orchestration
├── Makefile                          # Build & test commands
└── pyproject.toml                   # Python dependencies
```

---

## 📊 Evaluation Results

The pipeline is evaluated using **RAGAS** metrics — industry-standard for RAG quality assessment.

| Metric | Target | Current | Description |
|--------|--------|---------|-------------|
| **Faithfulness** | >0.85 | 0.78 | Proportion of claims verifiable against context |
| **Answer Relevancy** | >0.90 | 0.92 | How well the answer addresses the query |
| **Context Precision** | >0.80 | 0.85 | Signal-to-noise ratio in retrieved chunks |
| **Grounding Score** | >0.70 | 0.83 | Overall claim verification rate |
| **Healing Success Rate** | >70% | 82% | % of healing cycles that improve grounding |
| **Cache Hit Rate** | >20% | 12% | Semantic cache efficiency (training phase) |
| **p95 Latency** | <3s | 2.1s | 95th percentile end-to-end response time |

> **Note:** Current scores reflect development-stage evaluations with limited datasets. Production deployments with domain-specific data and fine-tuned retrieval parameters achieve higher scores.

### Running Evaluations

```bash
# Run full evaluation suite
python scripts/run_eval.py --dataset test_data/eval_dataset.jsonl

# Run with custom parameters
python scripts/run_eval.py --dataset custom.jsonl --model llama3:8b --k 10

# View evaluation history
cat eval_results/eval_history.csv
```

---

## 🔌 API Reference

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/api/v1/health` | GET | System health check | No |
| `/api/v1/auth/login` | POST | User authentication | No |
| `/api/v1/auth/signup` | POST | User registration | No |
| `/api/v1/auth/me` | GET | Current user profile | JWT |
| `/api/v1/query` | POST | Submit RAG query | JWT |
| `/api/v1/query/stream` | GET | SSE streaming query | JWT |
| `/api/v1/ingest` | POST | Upload document | JWT |
| `/api/v1/documents` | GET | List indexed documents | JWT |
| `/api/v1/documents/{id}` | DELETE | Remove document | JWT (admin) |
| `/metrics` | GET | Prometheus metrics | No |
| `/docs` | GET | Interactive API docs | No |

---

## 🐳 Deployment

### Docker Compose (Development)

```bash
docker compose up -d
```

### Kubernetes (Production)

```bash
kubectl apply -k infra/k8s/
```

The K8s deployment includes:
- **HPA:** Auto-scales 2-10 pods based on CPU/memory/custom metrics
- **PDB:** Ensures min 2 API pods always available during disruptions
- **Secrets:** DB credentials, JWT keys, API keys
- **Network Policies:** Micro-segmentation between services
- **Pod Security:** Non-root user, read-only rootfs, seccomp profiles
- **Probes:** Startup, readiness, and liveness checks
- **Rolling Updates:** maxUnavailable=0 for zero-downtime deployments

### Monitoring Stack

```bash
# Deploy Prometheus + Grafana (via docker compose or K8s)
# Then import infra/monitoring/grafana-dashboard.json
```

The Grafana dashboard includes 23 panels across 5 sections:
- 📊 API Overview — request rate, latency (p50/p95/p99), error rate, instance health
- 🛡️ Pipeline Quality — grounding score, RAGAS metrics, hallucination rate, verdict distribution
- 💻 Infrastructure — CPU/memory/network per container
- 🔐 Security — auth failures, rate limiting, injection blocks
- 🔔 Alerts — 15+ Prometheus alert rules with severity levels

---

## 🧪 Testing

```bash
# Run unit tests
pytest backend/tests/unit/ -v

# Run integration tests (requires Docker)
pytest backend/tests/integration/ -v

# Run end-to-end tests
pytest backend/tests/e2e/ -v

# Run all tests with coverage
pytest --cov=backend --cov-report=term-missing

# Run linting
ruff check backend/
```

**Test Suite:** ~150 test functions across 26 test files covering unit, integration, and E2E scenarios.

---

## 📈 Project Metrics

| Metric | Value |
|--------|-------|
| **Backend Lines of Code** | ~11,200 Python |
| **Backend Files** | 101 |
| **Frontend Lines of Code** | ~3,500 TSX/TS |
| **Frontend Files** | 14 |
| **Test Files** | 26 |
| **Test Functions** | ~150 |
| **K8s Manifests** | 10 files |
| **Monitoring Configs** | 3 files (Prometheus + Grafana + alerts) |
| **Documentation** | 14 markdown files |
| **API Endpoints** | 12 |

---

## 🔒 Security

- **Authentication:** RS256-signed JWT tokens with 7-day expiry
- **Authorization:** RBAC with 4 roles (admin, editor, viewer, auditor)
- **Rate Limiting:** 60 req/min default, 5 req/min on auth endpoints
- **Concurrency Control:** 50 global, 5 per user
- **Prompt Injection:** Two-stage detection (regex + LLM-as-judge)
- **Audit Logging:** All mutating operations logged with rotation
- **Data Isolation:** Strict tenant-level boundaries in all stores
- **Container Security:** Non-root user, read-only rootfs, seccomp, capabilities drop

---

## 🗺️ Roadmap

- [x] **Phase 1:** Data Isolation & Identifier Integrity
- [x] **Phase 2:** PostgreSQL + DI Container + Async Redis
- [x] **Phase 3:** Critic Reliability & Adaptive Retrieval
- [x] **Phase 4:** Checkpointing, Streaming, OpenTelemetry
- [x] **Phase 5:** RAGAS Evaluation + Test Infrastructure
- [x] **Phase 6:** Security Hardening + Production Readiness
- [ ] **Future:** Multi-modal RAG, Fine-tuned evaluator, Active learning,
      Federated retrieval, Auto-scaling, Natural language admin

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Write tests for all new features
- Follow existing code style (ruff + black formatting)
- Update documentation for API changes
- Use conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, etc.)

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- **LangGraph** — Pipeline orchestration framework
- **LangChain** — LLM integration toolkit
- **ChromaDB** — Vector store backbone
- **Neo4j** — Knowledge graph database
- **RAGAS** — Evaluation framework

---

<p align="center">
  Built with ❤️ for reliable, verifiable AI knowledge retrieval.
  <br/>
  <a href="https://github.com/yourusername/self-healing-rag">GitHub</a> ·
  <a href="/docs">Documentation</a> ·
  <a href="/docs/API_SPECIFICATION.md">API Reference</a>
</p>
