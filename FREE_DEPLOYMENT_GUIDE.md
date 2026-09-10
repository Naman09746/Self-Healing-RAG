# 🌐 Zero-Dollar ($0/Month) Cloud Deployment Guide

This guide walks you step-by-step through deploying the full **Self-Healing RAG** system to the cloud for **100% FREE ($0/month)**, with zero hardware strain on your local machine.

---

## 🏗️ Architecture Blueprint ($0 Free Tiers)

| Component | Free Provider | Free Tier Specification | Cost |
| :--- | :--- | :--- | :--- |
| **Frontend UI** | [Vercel](https://vercel.com) | Unlimited edge deployments, global CDN, zero cold start | **$0** |
| **Backend API** | [Render](https://render.com) or [Hugging Face](https://huggingface.co) | 512MB RAM Web Service (Render) or 16GB RAM CPU Space (HF) | **$0** |
| **PostgreSQL** | [Neon.tech](https://neon.tech) | 0.5 GB Serverless Postgres 16, auto-scaling, pooled URLs | **$0** |
| **Vector DB** | **pgvector** on Neon Postgres | HNSW index on `vector_chunks`, reuses PG (no extra server) | **$0** |
| **Session Store** | **pg** `session_messages` on Neon | Reuses Postgres, no Redis needed (Upstash optional) | **$0** |
| **Sparse Retrieval** | **pg tsvector** on Neon | `sparse_chunks` GIN index, no BM25 rebuild | **$0** |
| **Reranker** | **none** (RRF only) | No 80MB cross-encoder, fits 512M RAM | **$0** |
| **Graph** | **In-Memory** | No 1Gi Neo4j container | **$0** |
| **Redis Cache** | [Upstash](https://upstash.com) *(optional)* | Serverless Redis, 10k cmds/day — only if `SESSION_STORE_PROVIDER=redis` | **$0** |
| **LLM Inference** | [Groq Cloud](https://console.groq.com) | Llama 3.3 70B & 8B, 30 req/min, ~300 tokens/sec | **$0** |

> [!TIP]
> **Why this won't freeze your laptop:**
> Yesterday, running Ollama + 4 Docker containers locally saturated your Mac's RAM and swap space. In this cloud setup, all compute and memory are offloaded to high-performance cloud providers without costing a single penny.

---

## 📋 Step 1: Get Free Groq API Key (30 Seconds)

1. Go to [console.groq.com](https://console.groq.com) and sign up with GitHub or Google.
2. Navigate to **API Keys** → click **Create API Key**.
3. Copy your key (starts with `gsk_...`). Save it for Step 4.

---

## 🗄️ Step 2: Create Free Neon PostgreSQL Database (1 Minute)

1. Go to [neon.tech](https://neon.tech) and sign up for the free tier.
2. Click **Create Project** (e.g. name it `self-healing-rag`).
3. Under **Connection Details**, copy the **Connection string**:
   ```
   postgresql://user:password@ep-xyz.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
   *(Our backend automatically converts `postgresql://` to `postgresql+asyncpg://` behind the scenes).*

---

## ⚡ Step 3: Free-Tier Pluggable Stores (No Extra Containers)

**Defaults are $0 with no Redis/Neo4j/Qdrant needed** — all reuse Neon Postgres:

| Store | Free-Tier Default | Paid Alternative |
|---|---|---|
| `VECTOR_STORE_PROVIDER` | `pgvector` | `qdrant` (`--profile qdrant`), `pinecone` |
| `SESSION_STORE_PROVIDER` | `pg` | `redis` (Upstash) |
| `SPARSE_PROVIDER` | `pg_tsvector` | `bm25` (in-memory) |
| `RERANKER_PROVIDER` | `none` | `cross-encoder` |
| `GRAPH_PROVIDER` | `memory` | `neo4j` (`--profile graph`) |

**Optional Step 3a: Upstash Redis (only if you prefer Redis over Postgres sessions)**

1. Go to [upstash.com](https://upstash.com) and sign up for free.
2. Click **Create Database** → select region closest to your Neon DB.
3. Copy `REDIS_URL` (`rediss://default:xxxx@yyyy.upstash.io:6379`) and set `SESSION_STORE_PROVIDER=redis`.

---

## 🚀 Step 4: Deploy Backend API to Render (Free Web Service)

1. Push your latest code to your GitHub repository:
   ```bash
   git add .
   git commit -m "feat: cloud deployment readiness"
   git push origin main
   ```
2. Go to [render.com](https://render.com) → **New** → **Web Service**.
3. Connect your GitHub repository.
4. Set the following build and start configurations:
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -e .`
   - **Start Command**: `uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT`
   *(Alternatively, choose **Docker** and point to `infra/docker/Dockerfile.api`).*
5. Under **Environment Variables**, add the following:

| Key | Value / Example | Notes |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `openai` | Routes to Groq via OpenAI compatibility |
| `OPENAI_API_KEY` | `gsk_...` | Your Groq API Key |
| `OPENAI_BASE_URL` | `https://api.groq.com/openai/v1` | Groq's high-speed API gateway |
| `MODEL_NAME` | `llama-3.3-70b-versatile` | Ultra-fast flagship Llama 3.3 |
| `DATABASE_URL` | `postgresql://user:pwd@ep-xyz.neon.tech/neondb?sslmode=require` | Your Neon connection string |
| `LANGGRAPH_CHECKPOINT_URI` | `postgresql://user:pwd@ep-xyz.neon.tech/neondb?sslmode=require` | Checkpointer database URI |
| `VECTOR_STORE_PROVIDER` | `pgvector` | Free-tier pgvector (no extra server) |
| `SESSION_STORE_PROVIDER` | `pg` | Free-tier Postgres sessions (or `redis` for Upstash) |
| `SPARSE_PROVIDER` | `pg_tsvector` | Free-tier Postgres tsvector |
| `RERANKER_PROVIDER` | `none` | Free-tier RRF only (or `cross-encoder`) |
| `GRAPH_PROVIDER` | `memory` | Free-tier in-memory (or `neo4j`) |
| `REDIS_URL` | `rediss://default:pwd@xyz.upstash.io:6379` | Only if `SESSION_STORE_PROVIDER=redis` |
| `CORS_ORIGINS` | `*` | Allows browser calls from Vercel |
| `JWT_ALGORITHM` | `RS256` | Secure RSA algorithm |

6. Click **Deploy Web Service**.
7. Once deployed, copy your Render public URL (e.g. `https://self-healing-rag-api.onrender.com`).
8. Test that it's live: open `https://self-healing-rag-api.onrender.com/health` in your browser.

---

## 🎨 Step 5: Deploy Frontend to Vercel (1 Minute)

1. Go to [vercel.com](https://vercel.com) → Click **Add New Project**.
2. Import your GitHub repository.
3. In **Root Directory**, click edit and select `frontend`.
4. Under **Environment Variables**, add:
   - `NEXT_PUBLIC_API_URL`: `https://self-healing-rag-api.onrender.com/api/v1`
   - `NEXT_PUBLIC_WS_URL`: `wss://self-healing-rag-api.onrender.com`
5. Click **Deploy**.

Within 60 seconds, your frontend will be live worldwide on `https://your-project.vercel.app`!

---

## 🔍 Verification & Health Check

1. Open your Vercel URL in your browser.
2. Go to **Settings** → click **Test Ping**.
3. You will see a live diagnostic test querying `/health` across PostgreSQL, Redis, and LLM services with green checkmarks.
4. Go to **Document Vault**, upload a document, and ask queries in **Query Lab**.
