# Application Flow — Self-Healing RAG Pipeline

## Complete User Journey

```mermaid
flowchart TB
    ENTRY["User arrives at /chat"] --> AUTH{Authenticated?}
    AUTH -->|No| LOGIN["Login / Signup Screen"]
    AUTH -->|Yes| QUERY["Query Input Screen"]
    
    LOGIN --> AUTH_CHECK{Valid credentials?}
    AUTH_CHECK -->|Yes| QUERY
    AUTH_CHECK -->|No| LOGIN_ERROR["Show error → retry"]

    QUERY --> SUBMIT["User submits query"]
    SUBMIT --> LOADING["Spinner + Phase Progress Bar"]
    
    subgraph RAG_PIPELINE["RAG Pipeline (Server)"]
        PHASE1["Phase 1: Intake<br/>Validate + enrich query"]
        PHASE2["Phase 2: Plan<br/>Classify complexity<br/>(simple/medium/complex)"]
        PHASE3["Phase 3: Retrieve<br/>Dense + Sparse + Graph<br/>Adaptive k={3,5,10}"]
        PHASE4["Phase 4: Generate<br/>LLM answer with context"]
        PHASE5["Phase 5: Critic<br/>Extract claims → verify grounding"]
        PHASE6{"Grounded ≥50%?"}
        PHASE7["Phase 6: Heal<br/>Expand retrieval / rewrite query"]
        PHASE8["Phase 7: Output<br/>Format + return result"]
    end
    
    LOADING --> PHASE1
    PHASE1 --> PHASE2
    PHASE2 --> PHASE3
    PHASE3 --> PHASE4
    PHASE4 --> PHASE5
    PHASE5 --> PHASE6
    PHASE6 -->|Yes| PHASE8
    PHASE6 -->|No| PHASE7
    PHASE7 --> PHASE3
    
    PHASE8 --> RESULT["Answer displayed with:<br/>- Sources & citations<br/>- Confidence score<br/>- Phase timings<br/>- Healing indicators"]
    
    RESULT --> FEEDBACK{"User feedback?"}
    FEEDBACK -->|Thumbs up| DONE["Session complete"]
    FEEDBACK -->|Thumbs down| REGENERATE["Re-query with adjusted params"]
    FEEDBACK -->|New query| QUERY
    REGENERATE --> SUBMIT
```

## Entry Points

| Entry Point | URL | Auth Required | Description |
|-------------|-----|---------------|-------------|
| **Web Chat** | `/chat` | Yes | Primary RAG query interface |
| **API Query** | `POST /api/v1/query/rag` | Yes (Bearer) | Programmatic query access |
| **WebSocket** | `ws://host/ws?token={jwt}` | Yes (query param) | Streaming token-by-token response |
| **Health Check** | `GET /health` | No | Liveness + readiness probe |
| **Admin Dashboard** | `/admin/*` | Yes (admin+) | User management, audit log, eval runs |

## Navigation Flow

```mermaid
flowchart LR
    HOME["/"] --> CHAT["/chat"]
    HOME --> DASH["/dashboard"]
    HOME --> ADMIN["/admin"]
    
    CHAT --> QUERY_PAGE["Query page<br/>+ streaming result"]
    DASH --> STATS["Metrics & charts"]
    DASH --> EVAL_RESULTS["Evaluation results table"]
    
    ADMIN --> ADMIN_USERS["/admin/users<br/>List, add, edit users"]
    ADMIN --> ADMIN_AUDIT["/admin/audit<br/>Audit log viewer"]
    ADMIN --> ADMIN_EVAL["/admin/eval<br/>Run benchmarks"]
    ADMIN --> ADMIN_DOCS["/admin/documents<br/>Ingested doc list"]
```

## Authentication Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant API as API Server
    participant DB as PostgreSQL
    participant AUDIT as Audit Logger

    U->>F: Enter email + password
    F->>API: POST /api/v1/auth/login
    API->>DB: SELECT user WHERE email=?
    DB-->>API: User row (or None)
    API->>API: verify_password(plain, hash)
    alt Valid credentials
        API->>AUDIT: log_user_login(email, ip, user_agent)
        API-->>F: { access_token: "eyJ...", token_type: "bearer" }
        F->>F: Store token in localStorage
        F-->>U: Redirect to /chat
    else Invalid credentials
        API->>AUDIT: log_auth_failure(email, ip, "Invalid credentials")
        API-->>F: 401 Unauthorized
        F-->>U: Show error message
    end

    Note over U,F: Every subsequent request
    F->>F: Read token from localStorage
    F->>API: GET /api/v1/query/rag (Authorization: Bearer eyJ...)
    API->>API: decode_access_token(token)
    API->>API: verify RS256 signature
    API->>API: check RBAC permission
    alt Token valid + authorized
        API-->>F: 200 response
    else Token expired
        API-->>F: 401 → redirect to login
    end
```

## Main Feature Flows

### Query Flow (Synchronous)

```mermaid
sequenceDiagram
    participant C as Client
    participant MW as Middleware
    participant API as API Server
    participant LC as LLMClient
    participant STORE as Storage Layer
    participant EVAL as RAGASEvaluator

    C->>MW: POST /api/v1/query/rag { query, tenant_id }
    MW->>MW: Attach RequestID
    MW->>MW: Check auth (Bearer token)
    MW->>MW: Rate limit check
    MW->>MW: Concurrency check
    MW->>MW: Prompt injection detect
    MW->>MW: Log audit event
    
    MW->>API: Forward request
    API->>API: Semantic cache lookup
    alt Cache hit
        API-->>C: Cached response
    else Cache miss
        API->>LC: Generate answer via RAG pipeline
        LC->>STORE: Dense + Sparse + Graph retrieval
        STORE-->>LC: Chunks + entities
        LC->>LC: Generate answer
        LC->>LC: Critic → Heal loop
        LC-->>API: Final answer + metadata
        
        par Optional evaluation
            API->>EVAL: Score (faithfulness, relevancy, precision)
        end
        
        API->>API: Store in semantic cache
        API-->>C: { answer, sources, phase_timings, healing_actions }
    end
```

### Streaming Query Flow (WebSocket)

```mermaid
sequenceDiagram
    participant C as Client
    participant WS as WebSocket Handler
    participant GRAPH as LangGraph Pipeline
    participant LLM as Ollama LLM

    C->>WS: ws://host/ws?token={jwt}
    WS->>WS: Verify token
    WS-->>C: Connection established (phase:connecting)
    
    C->>WS: { query: "What is RAG?", tenant_id: "default" }
    WS->>GRAPH: Start async stream
    
    GRAPH->>WS: event: phase, data: { phase: "intake", status: "started" }
    WS-->>C: SSE: phase intake started
    
    GRAPH->>WS: event: phase, data: { phase: "planning", status: "started" }
    WS-->>C: SSE: phase planning started
    
    GRAPH->>WS: event: phase, data: { phase: "retrieval", status: "started" }
    WS-->>C: SSE: phase retrieval started
    GRAPH->>WS: event: phase, data: { phase: "retrieval", status: "complete", chunks: 5 }
    WS-->>C: SSE: phase retrieval complete
    
    GRAPH->>WS: event: phase, data: { phase: "generation", status: "started" }
    WS-->>C: SSE: phase generation started
    loop Token stream
        GRAPH->>LLM: Next token
        LLM-->>GRAPH: Token chunk
        GRAPH->>WS: event: token, data: { text: "Retrieval" }
        WS-->>C: SSE: "Retrieval"
    end
    GRAPH->>WS: event: phase, data: { phase: "generation", status: "complete" }
    WS-->>C: SSE: phase generation complete
    
    GRAPH->>WS: event: phase, data: { phase: "critic", status: "started" }
    WS-->>C: SSE: phase critic started
    GRAPH->>WS: event: phase, data: { phase: "critic", status: "complete", grounded_pct: 85 }
    WS-->>C: SSE: phase critic complete
    
    GRAPH->>WS: event: phase, data: { phase: "output", status: "complete" }
    WS-->>C: SSE: phase output complete
    
    GRAPH->>WS: event: metadata, data: { total_tokens, model, phase_timings }
    WS-->>C: SSE: metadata
    GRAPH->>WS: event: done
    WS-->>C: SSE: done
```

### Ingestion Flow

```mermaid
sequenceDiagram
    participant U as User (Editor+)
    participant API as API Server
    participant CHUNK as Chunker
    participant STORE as Storage Layer
    participant GRAPH as Graph Extractor

    U->>API: POST /api/v1/ingest/upload (file + tenant_id)
    API->>API: RBAC check (require: ingest:document)
    API->>API: Validate file type (PDF, TXT, MD)
    API->>CHUNK: Split into chunks (size=1000, overlap=200)
    CHUNK-->>API: List[DocumentChunk]
    
    par Store embeddings
        API->>STORE: ChromaDB: upsert_embeddings(chunks)
    and Store sparse index
        API->>STORE: BM25: add_to_corpus(chunks)
    and Extract entities
        API->>GRAPH: Neo4j: extract_entities_and_relations(chunks)
    end
    
    API->>API: Log to audit (document_id, chunk_count, tenant_id)
    API-->>U: 201 { document_id, chunk_count, status: "indexed" }
```

### Evaluation Flow

```mermaid
sequenceDiagram
    participant CLI as CLI / Admin
    participant Q as EvaluationQueue (Redis)
    participant RUN as EvaluationRunner
    participant EVAL as RAGASEvaluator
    participant DB as PostgreSQL / CSV

    CLI->>Q: enqueue(dataset_path, limit=100)
    Q->>Q: Create job (status=QUEUED)
    Q-->>CLI: job_id: "eval_abc123"
    
    RUN->>Q: poll_for_jobs()
    Q-->>RUN: job_id: "eval_abc123"
    RUN->>Q: update_status(job_id, PROCESSING)
    
    RUN->>RUN: load_dataset(dataset_path)
    RUN->>RUN: for each sample in dataset:
    
    loop For each sample
        RUN->>RUN: simulate_query(sample.query)
        RUN->>RUN: collect answer + retrieved contexts
        RUN->>EVAL: compute_faithfulness(answer, contexts)
        RUN->>EVAL: compute_answer_relevancy(query, answer)
        RUN->>EVAL: compute_context_precision(query, contexts)
        EVAL-->>RUN: { faith, rel, prec } scores
        RUN->>RUN: append to results list
    end
    
    RUN->>RUN: compute aggregate stats
    RUN->>DB: save_report(report)
    RUN->>Q: update_status(job_id, COMPLETED)
    Q-->>CLI: Report ready: eval_results/eval_abc123.json
```

## Error Handling Flow

```mermaid
flowchart TB
    ERR["Error Occurs"] --> TYPE{Error Type}
    
    TYPE -->|401| AUTH_ERR["Auth Error"]
    TYPE -->|429| RATE_ERR["Rate Limit"]
    TYPE -->|503| CONC_ERR["Concurrency"]
    TYPE -->|422| VALID_ERR["Validation"]
    TYPE -->|500| SERVER_ERR["Server Error"]
    
    AUTH_ERR --> AUTH_RESP["Response: 401<br/>Body: { detail, code }<br/>Frontend: redirect to /login"]
    RATE_ERR --> RATE_RESP["Response: 429<br/>Headers: Retry-After<br/>Body: retry_after_seconds<br/>Frontend: show cooldown timer"]
    CONC_ERR --> CONC_RESP["Response: 503<br/>Body: { error, retry_after }<br/>Frontend: queue request, retry"]
    VALID_ERR --> VALID_RESP["Response: 422<br/>Body: { detail: [field errors] }<br/>Frontend: highlight invalid fields"]
    SERVER_ERR --> SERVER_RESP["Response: 500<br/>Body: { detail, trace_id }<br/>Frontend: show generic error + support ID"]
    
    SERVER_ERR --> LOG["Log: error + trace_id + stack<br/>Audit: log event<br/>OTel: record error span"]
    
    subgraph REDIRECT["Post-Error Recovery"]
        RETRY_RATE["Rate limited: wait Retry-After seconds"]
        RETRY_CONC["Concurrency blocked: auto-retry with backoff"]
        RETRY_AUTH["Token expired: refresh token → retry"]
    end
    
    RATE_RESP --> RETRY_RATE
    CONC_RESP --> RETRY_CONC
    AUTH_RESP --> RETRY_AUTH
```

## Admin Flow

```mermaid
sequenceDiagram
    participant A as Admin User
    participant F as Frontend
    participant API as API Server
    participant DB as PostgreSQL
    participant AUDIT as Audit Logger

    Note over A,F: User Management
    A->>F: Navigate to /admin/users
    F->>API: GET /api/v1/auth/users
    API->>API: RBAC check (require: users:manage)
    API->>DB: SELECT * FROM users
    DB-->>API: User list
    API-->>F: JSON user list
    F-->>A: Table of users with roles
    
    A->>F: Click "Change Role" on user
    F->>API: PATCH /api/v1/auth/users/{id} { role: "editor" }
    API->>API: RBAC check (require: roles:manage)
    API->>DB: UPDATE users SET role=?
    API->>AUDIT: log role change (admin_email, target_email, old_role, new_role)
    DB-->>API: Success
    API-->>F: 200 OK
    F-->>A: Role updated in table

    Note over A,F: Audit Log Viewing
    A->>F: Navigate to /admin/audit
    F->>API: GET /api/v1/audit/logs?limit=50&offset=0
    API->>API: RBAC check (require: audit:view)
    API->>DB: Read audit_logs table or files
    DB-->>API: Log entries
    API-->>F: Paginated log entries
    F-->>A: Filterable log table

    Note over A,F: Evaluation
    A->>F: Navigate to /admin/eval
    F->>API: GET /api/v1/eval/runs
    API-->>F: Previous evaluation run history
    A->>F: Click "Run Evaluation"
    F->>API: POST /api/v1/eval/run { dataset: "default" }
    API->>API: Enqueue evaluation job
    API-->>F: { job_id, status: "queued" }
    F-->>A: "Evaluation queued — check back"
    
    loop Poll every 5s
        F->>API: GET /api/v1/eval/jobs/{job_id}
        API-->>F: { status: "processing" }
    end
    
    API-->>F: { status: "completed", results_url }
    F-->>A: Show results summary with metrics