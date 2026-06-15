# API Specification — Self-Healing RAG Pipeline

## Base URL

| Environment | URL |
|-------------|-----|
| **Development** | `http://localhost:8000` |
| **Staging** | `https://api.staging.sel healing-rag.example.com` |
| **Production** | `https://api.sel healing-rag.example.com` |

## Common Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes (except `/auth/*`) | `Bearer <jwt_token>` |
| `Content-Type` | Yes | `application/json` |
| `X-Request-ID` | No | Optional trace ID; auto-generated if omitted |
| `X-Tenant-ID` | Yes (for multi-tenant) | Tenant UUID |

## Common Response Formats

### Success

```json
{
  "data": { ... },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2025-06-13T19:30:00Z"
  }
}
```

### Error

```json
{
  "detail": "Human-readable error message",
  "code": "ERROR_CODE",
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2025-06-13T19:30:00Z"
  }
}
```

### Pagination

```json
{
  "data": [ ... ],
  "meta": {
    "page": 1,
    "per_page": 50,
    "total": 250,
    "total_pages": 5,
    "has_next": true,
    "has_prev": false
  }
}
```

## Error Codes

| HTTP Status | Code | Description |
|-------------|------|-------------|
| 400 | `BAD_REQUEST` | Malformed request body or parameters |
| 401 | `UNAUTHORIZED` | Missing or invalid authentication token |
| 401 | `TOKEN_EXPIRED` | JWT has expired |
| 403 | `FORBIDDEN` | Authenticated but insufficient permissions |
| 404 | `NOT_FOUND` | Requested resource does not exist |
| 409 | `CONFLICT` | Resource already exists (e.g., duplicate email) |
| 422 | `VALIDATION_ERROR` | Request body failed schema validation |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests; see `Retry-After` header |
| 503 | `SERVICE_UNAVAILABLE` | Server overloaded (concurrency limit); retry after `retry_after_seconds` |

---

## Authentication

### POST /api/v1/auth/signup

Create a new user account.

**Rate Limit:** 5 req/min per IP  
**Auth:** None

#### Request Body

```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "full_name": "Jane Doe",
  "tenant_id": "uuid-abc-123"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | Valid email address |
| `password` | string | Yes | Min 8 characters |
| `full_name` | string | No | User's display name |
| `tenant_id` | string | No | Existing tenant ID; if omitted, creates new tenant |

#### Response: 201 Created

```json
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "Jane Doe",
  "is_active": true,
  "user_uuid": "uuid-def-456",
  "tenant_id": "uuid-abc-123",
  "role": "viewer"
}
```

#### Error: 409 Conflict

```json
{
  "detail": "A user with this email already exists",
  "code": "CONFLICT"
}
```

---

### POST /api/v1/auth/login

Authenticate and receive a JWT token.

**Rate Limit:** 5 req/min per IP  
**Auth:** None

#### Request Body (application/x-www-form-urlencoded)

```
grant_type=&username=user@example.com&password=SecurePass123!
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | Yes | Email address |
| `password` | string | Yes | Account password |
| `grant_type` | string | No | Must be `password` if provided |

#### Response: 200 OK

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "token_type": "bearer"
}
```

#### Error: 401 Unauthorized

```json
{
  "detail": "Incorrect email or password",
  "code": "UNAUTHORIZED"
}
```

---

### GET /api/v1/auth/me

Returns the currently authenticated user's profile.

**Rate Limit:** 60 req/min  
**Auth:** Bearer Token  
**Roles:** Any authenticated

#### Response: 200 OK

```json
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "Jane Doe",
  "is_active": true,
  "user_uuid": "uuid-def-456",
  "tenant_id": "uuid-abc-123",
  "role": "editor"
}
```

---

## Query

### POST /api/v1/query/rag

Execute a RAG query and receive a generated answer.

**Rate Limit:** 60 req/min  
**Auth:** Bearer Token  
**Roles:** admin, editor, viewer

#### Request Body

```json
{
  "query": "What is the summary of project Omega?",
  "tenant_id": "uuid-abc-123",
  "top_k": 5,
  "stream": false,
  "session_id": "session_xyz"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | Yes | — | The user's question |
| `tenant_id` | string | Yes | — | Tenant context for retrieval |
| `top_k` | integer | No | 5 | Number of retrieval chunks (3/5/10 adaptive) |
| `stream` | boolean | No | false | Use SSE streaming endpoint instead |
| `session_id` | string | No | null | Session for context continuity |

#### Response: 200 OK

```json
{
  "answer": "Project Omega is a strategic initiative focused on...",
  "sources": [
    {
      "document_id": "doc_123",
      "document_name": "project_omega_spec.pdf",
      "chunk_index": 4,
      "score": 0.89,
      "content": "...Project Omega was launched in Q1 2025..."
    },
    {
      "document_id": "doc_123",
      "document_name": "project_omega_spec.pdf",
      "chunk_index": 7,
      "score": 0.76,
      "content": "...key milestones include..."
    }
  ],
  "phase_timings": {
    "intake_ms": 5,
    "planning_ms": 12,
    "retrieval_ms": 145,
    "generation_ms": 2340,
    "critic_ms": 890,
    "total_ms": 3392
  },
  "healing_actions": [],
  "confidence": 0.85,
  "model": "mistral:7b",
  "total_tokens": 512
}
```

#### Error: 422 Validation Error

```json
{
  "detail": [
    {
      "loc": ["body", "query"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ],
  "code": "VALIDATION_ERROR"
}
```

---

## WebSocket /ws

Streaming RAG query with real-time phase updates and token-by-token generation.

**Auth:** JWT token passed as query parameter: `ws://host/ws?token=eyJ...`  
**Roles:** admin, editor, viewer

### Connection

```
WebSocket URL: ws://localhost:8000/ws?token=eyJhbGciOiJSUzI1NiIs...
```

### Client → Server Message

```json
{
  "query": "What is the summary of project Omega?",
  "tenant_id": "uuid-abc-123",
  "session_id": "session_xyz"
}
```

### Server → Client Events

All events are JSON-encoded messages with an `event` field:

#### Phase Update

```json
{
  "event": "phase",
  "data": {
    "phase": "retrieval",
    "status": "started"
  }
}
```

```json
{
  "event": "phase",
  "data": {
    "phase": "retrieval",
    "status": "complete",
    "chunks": 5
  }
}
```

| Phases | Description |
|--------|-------------|
| `intake` | Query validation and enrichment |
| `planning` | Complexity classification |
| `retrieval` | Dense + sparse + graph retrieval |
| `generation` | LLM answer generation |
| `critic` | Claim extraction and grounding verification |
| `healing` | (If needed) retrieval expansion or query rewrite |
| `output` | Final formatting |

#### Token Stream

```json
{
  "event": "token",
  "data": {
    "text": "Project"
  }
}
```

#### Metadata

```json
{
  "event": "metadata",
  "data": {
    "total_tokens": 512,
    "model": "mistral:7b",
    "phase_timings": {
      "intake_ms": 5,
      "planning_ms": 12,
      "retrieval_ms": 145,
      "generation_ms": 2340,
      "critic_ms": 890
    }
  }
}
```

#### Done

```json
{
  "event": "done"
}
```

#### Error

```json
{
  "event": "error",
  "data": {
    "code": "INTERNAL_ERROR",
    "detail": "An unexpected error occurred"
  }
}
```

---

## Ingestion

### POST /api/v1/ingest/upload

Upload a document for indexing into the knowledge base.

**Rate Limit:** 60 req/min  
**Auth:** Bearer Token  
**Roles:** admin, editor

#### Request (multipart/form-data)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | PDF, TXT, or Markdown file (max 50 MB) |
| `tenant_id` | string | Yes | Target tenant |

#### Response: 201 Created

```json
{
  "document_id": "doc_uuid_456",
  "filename": "project_omega_spec.pdf",
  "content_type": "application/pdf",
  "chunk_count": 24,
  "status": "indexed"
}
```

### GET /api/v1/ingest/documents

List all ingested documents for the current tenant.

**Rate Limit:** 60 req/min  
**Auth:** Bearer Token  
**Roles:** admin, editor, viewer

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `per_page` | integer | 50 | Items per page (max 100) |
| `sort_by` | string | `uploaded_at` | Sort field |
| `sort_order` | string | `desc` | `asc` or `desc` |

#### Response: 200 OK

```json
{
  "data": [
    {
      "id": 1,
      "document_id": "doc_uuid_456",
      "filename": "project_omega_spec.pdf",
      "content_type": "application/pdf",
      "chunk_count": 24,
      "uploaded_at": "2025-06-13T19:30:00Z",
      "uploaded_by": "admin@example.com"
    }
  ],
  "meta": {
    "page": 1,
    "per_page": 50,
    "total": 12
  }
}
```

### GET /api/v1/ingest/documents/{document_id}

Get details for a specific document.

**Rate Limit:** 60 req/min  
**Auth:** Bearer Token  
**Roles:** admin, editor, viewer

#### Response: 200 OK

```json
{
  "id": 1,
  "document_id": "doc_uuid_456",
  "filename": "project_omega_spec.pdf",
  "content_type": "application/pdf",
  "chunk_count": 24,
  "uploaded_at": "2025-06-13T19:30:00Z",
  "uploaded_by": "admin@example.com"
}
```

#### Error: 404 Not Found

```json
{
  "detail": "Document not found",
  "code": "NOT_FOUND"
}
```

### DELETE /api/v1/ingest/documents/{document_id}

Delete a document and all associated chunks from all stores.

**Rate Limit:** 60 req/min  
**Auth:** Bearer Token  
**Roles:** admin

#### Response: 204 No Content

#### Error: 404 Not Found

```json
{
  "detail": "Document not found",
  "code": "NOT_FOUND"
}
```

---

## Evaluation

### POST /api/v1/eval/run

Start a new evaluation run on a benchmark dataset.

**Rate Limit:** 10 req/min  
**Auth:** Bearer Token  
**Roles:** admin

#### Request Body

```json
{
  "dataset_name": "default_benchmark",
  "limit": 100
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `dataset_name` | string | Yes | — | Name of benchmark dataset |
| `limit` | integer | No | null | Max samples to evaluate (null = all) |

#### Response: 202 Accepted

```json
{
  "job_id": "eval_abc123",
  "status": "queued",
  "dataset_name": "default_benchmark",
  "sample_count": 100,
  "created_at": "2025-06-13T19:30:00Z"
}
```

### GET /api/v1/eval/jobs/{job_id}

Get the status and results of an evaluation job.

**Rate Limit:** 60 req/min  
**Auth:** Bearer Token  
**Roles:** admin

#### Response: 200 OK (Processing)

```json
{
  "job_id": "eval_abc123",
  "status": "processing",
  "progress": {
    "completed": 45,
    "total": 100
  }
}
```

#### Response: 200 OK (Completed)

```json
{
  "job_id": "eval_abc123",
  "status": "completed",
  "dataset_name": "default_benchmark",
  "sample_count": 100,
  "avg_faithfulness": 0.87,
  "avg_answer_relevancy": 0.92,
  "avg_context_precision": 0.81,
  "results_url": "/api/v1/eval/results/eval_abc123.csv",
  "started_at": "2025-06-13T19:30:00Z",
  "completed_at": "2025-06-13T19:35:00Z"
}
```

### GET /api/v1/eval/runs

List all evaluation runs.

**Rate Limit:** 60 req/min  
**Auth:** Bearer Token  
**Roles:** admin

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `per_page` | integer | 20 | Items per page |

#### Response: 200 OK

```json
{
  "data": [
    {
      "run_id": "eval_abc123",
      "dataset_name": "default_benchmark",
      "sample_count": 100,
      "avg_faithfulness": 0.87,
      "avg_answer_relevancy": 0.92,
      "avg_context_precision": 0.81,
      "status": "completed",
      "started_at": "2025-06-13T19:30:00Z",
      "completed_at": "2025-06-13T19:35:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 5
  }
}
```

### GET /api/v1/eval/results/{run_id}

Download evaluation results as CSV.

**Rate Limit:** 60 req/min  
**Auth:** Bearer Token  
**Roles:** admin

#### Response: 200 OK

```
Content-Type: text/csv

query,expected_answer,faithfulness,answer_relevancy,context_precision,latency_ms,healing_triggered
"What is Project Omega?","Project Omega is...",0.89,0.94,0.85,3450,false
"Who is the CEO?","The CEO is...",0.76,0.88,0.72,2890,true
```

---

## Health

### GET /health

Returns system health status. Used for liveness and readiness probes.

**Rate Limit:** None  
**Auth:** None

#### Response: 200 OK

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 86400,
  "checks": {
    "postgres": "healthy",
    "redis": "healthy",
    "chroma": "healthy",
    "neo4j": "healthy",
    "ollama": "healthy"
  },
  "timestamp": "2025-06-13T19:30:00Z"
}
```

#### Response: 503 Service Unavailable (degraded)

```json
{
  "status": "degraded",
  "version": "1.0.0",
  "uptime_seconds": 86400,
  "checks": {
    "postgres": "healthy",
    "redis": "healthy",
    "chroma": "healthy",
    "neo4j": "unhealthy",
    "ollama": "healthy"
  },
  "timestamp": "2025-06-13T19:30:00Z"
}
```

---

## Rate Limiting

All rate-limited endpoints return the following headers:

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Max requests per window |
| `X-RateLimit-Remaining` | Requests remaining in current window |
| `X-RateLimit-Reset` | Unix timestamp when the window resets |
| `Retry-After` | Seconds to wait before retrying (only on 429) |

## Endpoint Summary

| Method | Path | Auth | Rate Limit | Roles |
|--------|------|------|------------|-------|
| POST | `/api/v1/auth/signup` | No | 5/min/IP | — |
| POST | `/api/v1/auth/login` | No | 5/min/IP | — |
| GET | `/api/v1/auth/me` | Yes | 60/min | any |
| POST | `/api/v1/query/rag` | Yes | 60/min | admin, editor, viewer |
| WS | `/ws` | Yes | — | admin, editor, viewer |
| POST | `/api/v1/ingest/upload` | Yes | 60/min | admin, editor |
| GET | `/api/v1/ingest/documents` | Yes | 60/min | admin, editor, viewer |
| GET | `/api/v1/ingest/documents/{id}` | Yes | 60/min | admin, editor, viewer |
| DELETE | `/api/v1/ingest/documents/{id}` | Yes | 60/min | admin |
| POST | `/api/v1/eval/run` | Yes | 10/min | admin |
| GET | `/api/v1/eval/jobs/{id}` | Yes | 60/min | admin |
| GET | `/api/v1/eval/runs` | Yes | 60/min | admin |
| GET | `/api/v1/eval/results/{id}` | Yes | 60/min | admin |
| GET | `/health` | No | None | — |