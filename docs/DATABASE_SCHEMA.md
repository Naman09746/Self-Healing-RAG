# Database Schema — Self-Healing RAG Pipeline

## Entity Relationship Diagram

```mermaid
erDiagram
    Tenant ||--o{ User : has
    User ||--o{ AuditLog : performs
    User ||--o{ Document : uploads
    Tenant ||--o{ Document : owns
    Document ||--o{ DocumentChunk : contains
    Document ||--o{ EvalRun : evaluated_in
    EvalRun ||--o{ EvalResult : contains
    EvalResult ||--o{ EvalMetric : measures
    
    User {
        int id PK
        string user_uuid UK "immutable UUID"
        string email UK
        string hashed_password
        string full_name nullable
        string tenant_id FK
        string role "admin|editor|viewer|auditor"
        bool is_active
        datetime created_at
        datetime updated_at
    }
    
    Tenant {
        string id PK "UUID"
        string name
        datetime created_at
        datetime updated_at
    }
    
    Document {
        int id PK
        string document_id UK "UUID"
        string tenant_id FK
        string filename
        string content_type
        int chunk_count
        int uploaded_by FK "User.id"
        datetime uploaded_at
    }
    
    DocumentChunk {
        int id PK
        string chunk_id UK "UUID"
        int document_id FK
        string tenant_id FK
        text content
        int chunk_index
        int token_count
        jsonb metadata
        datetime created_at
    }
    
    EvalRun {
        int id PK
        string run_id UK "UUID"
        string tenant_id FK "nullable, null=system-wide"
        string dataset_name
        int sample_count
        float avg_faithfulness
        float avg_answer_relevancy
        float avg_context_precision
        string status "QUEUED|PROCESSING|COMPLETED|FAILED"
        datetime started_at
        datetime completed_at
    }
    
    EvalResult {
        int id PK
        int eval_run_id FK
        string query
        string expected_answer nullable
        string generated_answer
        jsonb retrieved_contexts "array of context strings"
        float faithfulness
        float answer_relevancy
        float context_precision
        float latency_ms
        int healing_triggered "0 or 1"
        datetime created_at
    }
    
    EvalMetric {
        int id PK
        string metric_name "faithfulness|answer_relevancy|context_precision"
        string scope "per_query|aggregate"
        float value
        int eval_result_id FK nullable
        int eval_run_id FK nullable
        datetime recorded_at
    }
    
    AuditLog {
        int id PK
        string event_type "login|signup|auth_failure|query|ingest|role_change"
        string actor_email
        string actor_role
        string tenant_id FK
        string ip_address
        string user_agent nullable
        jsonb details nullable
        datetime created_at
    }
    
    QueryCache {
        string query_hash PK "MD5 of normalized query + tenant"
        string tenant_id FK
        text query
        jsonb response "cached answer + sources"
        datetime created_at
        int ttl_seconds
        index expiry_idx ON (created_at + ttl_seconds)
    }
```

## PostgreSQL Tables

### Users Table

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    user_uuid UUID NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL DEFAULT 'viewer' CHECK (role IN ('admin','editor','viewer','auditor')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
```

### Tenants Table

```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Documents Table

```sql
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    document_id UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    filename VARCHAR(512) NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    uploaded_by INTEGER NOT NULL REFERENCES users(id),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_documents_tenant ON documents(tenant_id);
CREATE INDEX idx_documents_uploaded_by ON documents(uploaded_by);
```

### Document Chunks Table

```sql
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    chunk_id UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

CREATE INDEX idx_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_chunks_tenant ON document_chunks(tenant_id);
```

### Evaluation Tables

```sql
CREATE TABLE eval_runs (
    id SERIAL PRIMARY KEY,
    run_id UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
    dataset_name VARCHAR(255) NOT NULL,
    sample_count INTEGER NOT NULL DEFAULT 0,
    avg_faithfulness DOUBLE PRECISION,
    avg_answer_relevancy DOUBLE PRECISION,
    avg_context_precision DOUBLE PRECISION,
    status VARCHAR(20) NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED','PROCESSING','COMPLETED','FAILED')),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_eval_runs_tenant ON eval_runs(tenant_id);
CREATE INDEX idx_eval_runs_status ON eval_runs(status);

CREATE TABLE eval_results (
    id SERIAL PRIMARY KEY,
    eval_run_id INTEGER NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    expected_answer TEXT,
    generated_answer TEXT NOT NULL,
    retrieved_contexts JSONB DEFAULT '[]',
    faithfulness DOUBLE PRECISION,
    answer_relevancy DOUBLE PRECISION,
    context_precision DOUBLE PRECISION,
    latency_ms DOUBLE PRECISION,
    healing_triggered BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_eval_results_run ON eval_results(eval_run_id);

CREATE TABLE eval_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(50) NOT NULL CHECK (metric_name IN ('faithfulness','answer_relevancy','context_precision')),
    scope VARCHAR(20) NOT NULL CHECK (scope IN ('per_query','aggregate')),
    value DOUBLE PRECISION NOT NULL,
    eval_result_id INTEGER REFERENCES eval_results(id) ON DELETE CASCADE,
    eval_run_id INTEGER REFERENCES eval_runs(id) ON DELETE CASCADE,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT check_eval_metric_scope CHECK (
        (scope = 'per_query' AND eval_result_id IS NOT NULL) OR
        (scope = 'aggregate' AND eval_run_id IS NOT NULL)
    )
);

CREATE INDEX idx_eval_metrics_name ON eval_metrics(metric_name);
CREATE INDEX idx_eval_metrics_run ON eval_metrics(eval_run_id);
```

### Audit Logs Table

```sql
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN (
        'login','signup','auth_failure','query','ingest','role_change','eval_run'
    )),
    actor_email VARCHAR(255) NOT NULL,
    actor_role VARCHAR(20),
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_event ON audit_logs(event_type);
CREATE INDEX idx_audit_logs_actor ON audit_logs(actor_email);
CREATE INDEX idx_audit_logs_tenant ON audit_logs(tenant_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at DESC);
```

### Query Cache Table

```sql
CREATE TABLE query_cache (
    query_hash VARCHAR(64) PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    response JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ttl_seconds INTEGER NOT NULL DEFAULT 3600
);

CREATE INDEX idx_cache_expiry ON query_cache((created_at + (ttl_seconds || ' seconds')::INTERVAL));
CREATE INDEX idx_cache_tenant ON query_cache(tenant_id);
```

## Redis Data Structures

### Semantic Cache

```
Key:   cache:{md5(query + tenant_id)}
Value: JSON response { answer, sources, phase_timings }
TTL:   3600 seconds (1 hour)
Type:  STRING
```

### Rate Limiter (Sliding Window)

```
Key:   ratelimit:{client_id}:{endpoint_path}
Value: Count of requests in window
TTL:   Window duration (60s default)
Type:  SORTED SET (score=timestamp, member=request_id)
```

```
Algorithm:
1. ZREMRANGEBYSCORE key -inf (now - window_seconds)
2. Count = ZCARD key
3. If count >= limit → REJECT
4. ZADD key now request_id
5. EXPIRE key window_seconds
```

### Concurrency Counter

```
Key:   concurrency:{user_id}
Value: Current concurrent request count
TTL:   60s (extended on each operation)
Type:  STRING (INCR/DECR)
```

```
Algorithm:
1. INCR key → count
2. If count > max_concurrent → DECR key → REJECT
3. Process request
4. DECR key on completion
```

### Evaluation Queue

```
Job creation:
  Key:   eval:queue
  Value: job_id
  Type:  LIST (LPUSH)

Job status:
  Key:   eval:job:{job_id}
  Value: JSON { status, dataset, progress, results_url }
  TTL:   7 days after completion
  Type:  STRING

Job progress:
  Key:   eval:progress:{job_id}
  Value: JSON { completed, total, current_metrics }
  Type:  STRING
```

## ChromaDB Collections

```
Collection Name: rag_collection__{sanitized_tenant_id}

Metadata:
  - tenant_id: string
  - hnsw:space: "cosine"
  - embedding_model: "nomic-embed-text"

Documents:
  - id: "{document_id}:{chunk_index}"
  - embedding: [768 floats] (nomic-embed-text)
  - metadata:
      tenant_id: str
      document_id: str
      document_name: str
      chunk_index: int
      content: str (truncated to 512 chars for display)
      token_count: int
```

## Neo4j Graph Schema

### Node Labels

```
Entity {
  id: string (UUID)
  name: string
  type: string (person, organization, concept, technology, location)
  description: string
  tenant_id: string
  created_at: datetime
}
```

### Relationship Types

```
(:Entity)-[:RELATED_TO { weight: float, context: string }]->(:Entity)
(:Entity)-[:MEMBER_OF { role: string }]->(:Entity)
(:Entity)-[:PART_OF]->(:Entity)
(:Entity)-[:LOCATED_IN]->(:Entity)
(:Entity)-[:MENTIONED_IN { document_id: string, chunk_index: int }]->(:Document)
```

## LangGraph Checkpoint Schema

```sql
-- Managed by LangGraph's PostgresSaver
CREATE TABLE langgraph_checkpoints (
    thread_id UUID NOT NULL,
    checkpoint_ns VARCHAR(255) NOT NULL DEFAULT '',
    checkpoint_id UUID NOT NULL,
    parent_checkpoint_id UUID,
    type VARCHAR(50),
    config JSONB,
    metadata JSONB,
    values JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE langgraph_checkpoint_writes (
    thread_id UUID NOT NULL,
    checkpoint_ns VARCHAR(255) NOT NULL DEFAULT '',
    checkpoint_id UUID NOT NULL,
    task_id UUID NOT NULL,
    idx INTEGER NOT NULL,
    channel VARCHAR(255) NOT NULL,
    type VARCHAR(50),
    value JSONB NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
```

## Migrations

All schema changes managed via Alembic. Migration files in `backend/alembic/versions/`.

```
Commands:
  make migrate     # Auto-generate migration from model changes
  make upgrade     # Apply migrations
  make downgrade   # Rollback last migration
  make reset-db    # Drop and recreate (dev only)