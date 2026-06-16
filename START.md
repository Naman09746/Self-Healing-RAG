# 🚀 Self-Healing RAG — Quick Start Guide

> Everything you need to get the full stack running locally.

---

## 📦 Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.10+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Docker | 24+ | `docker --version` |
| Docker Compose | v2+ | `docker compose version` |
| Ollama | latest | `ollama --version` |

---

## 🚀 Option 1: Full Stack (Docker) — Easiest

```bash
# 1. Clone
git clone https://github.com/Naman09746/Self-Healing-RAG.git
cd Self-Healing-RAG

# 2. Configure environment
cp .env.example .env
# Edit .env if needed (defaults work for local dev)

# 3. Start everything
docker compose up -d

# 4. Check it's running
docker compose ps

# 5. Open in browser
open http://localhost:3000    # Frontend
open http://localhost:8000    # API
open http://localhost:8000/docs  # API Docs
```

**What this starts:** API server + Frontend + ChromaDB + PostgreSQL + Redis + Neo4j

---

## 🚀 Option 2: Manual (Backend only)

```bash
# 1. Backend setup
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Start dependent services (Docker)
docker compose up -d chroma postgres redis neo4j

# 3. Run migrations
make db-upgrade

# 4. Start the API
make run-backend
# → http://localhost:8001

# 5. Terminal 2 — Start Frontend
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

---

## 🚀 Option 3: Quick (Frontend only — for UI work)

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
# (UI works with mock data if backend is off)
```

---

## 🔧 Essential Commands

### Backend
```bash
make run-backend        # Start API server
make test               # Run all tests
make lint               # Lint + type check
make db-upgrade         # Run DB migrations
make db-rollback        # Roll back migration
make eval-run           # Run evaluation
make eval-quick         # Quick evaluation test
```

### Frontend
```bash
npm run dev             # Start dev server (:3000)
npm run build           # Production build
npm run lint            # Lint check
```

### Docker
```bash
docker compose up -d               # Start all services
docker compose down                # Stop all services
docker compose logs -f api         # Watch API logs
docker compose logs -f frontend    # Watch frontend logs
docker compose restart api         # Restart API only
```

---

## 📍 Access Points

| Service | URL |
|---------|-----|
| **Frontend Dashboard** | http://localhost:3000 |
| **API** | http://localhost:8000 |
| **API Docs (Swagger)** | http://localhost:8000/docs |
| **Prometheus Metrics** | http://localhost:8000/metrics |
| **ChromaDB** | http://localhost:8001 |
| **Neo4j Browser** | http://localhost:7474 |
| **PostgreSQL** | localhost:5432 |
| **Redis** | localhost:6379 |

---

## 🧪 Quick Health Check

```bash
# API health
curl http://localhost:8000/health

# Frontend is up
curl -I http://localhost:3000

# Ingest a test document
curl -X POST http://localhost:8000/api/v1/ingest \
  -F "file=@test_data/q4_strategic_intelligence.pdf"

# Query
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the key findings?"}'
```

---

## 🧹 Clean Up

```bash
make clean              # Remove Python cache files
docker compose down -v  # Stop everything + delete volumes
rm -rf .venv            # Remove Python virtual env
rm -rf frontend/node_modules  # Remove frontend deps
```
