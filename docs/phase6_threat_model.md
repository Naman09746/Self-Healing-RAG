# Phase 6 — Security Architecture: Threat Model & Implementation

## 1. Threat Model

### Assets
| Asset | Description | Sensitivity |
|-------|-------------|-------------|
| JWT signing key | RS256 private key used to sign authentication tokens | **CRITICAL** |
| User credentials | Email/password pairs in PostgreSQL | **CRITICAL** |
| LLM API keys | OpenAI / LangSmith keys in env vars | **CRITICAL** |
| Database credentials | PostgreSQL username/password | **HIGH** |
| Redis credentials | Redis password (if set) | **HIGH** |
| RAG context data | Ingested documents, vectors | **MEDIUM** |
| Audit logs | User action history | **MEDIUM** |
| Session memory | User conversation history | **MEDIUM** |

### Threat Actors
| Actor | Capabilities | Motivation |
|-------|-------------|------------|
| External attacker | Network access, no credentials | Data exfiltration, privilege escalation |
| Unauthenticated user | API access without token | Access protected resources |
| Authenticated user | Valid JWT, limited role | Horizontal privilege escalation, data access beyond role |
| Malicious tenant | Valid tenant credentials | Cross-tenant data access |
| Insider (admin) | Administrative access | Audit bypass, data exfiltration |

### Threat Scenarios

| ID | Threat | Likelihood | Impact | Risk | Mitigation |
|----|--------|------------|--------|------|------------|
| T1 | HS256 key compromise via symmetric signing | Medium | **Critical** | **High** | RS256 asymmetric keys (§2) |
| T2 | Hardcoded secret fallback in source code | High | **Critical** | **High** | Remove fallback, fail closed (§2) |
| T3 | WebSocket without authentication | High | **High** | **High** | Add JWT validation to WS (§8) |
| T4 | Rate limiting bypass via IP rotation | Medium | Medium | Medium | Add user-based rate limiting (§3) |
| T5 | Redis without auth exposed to network | Medium | **High** | Medium | Redis password + TLS (§3) |
| T6 | Rate limiting disabled when Redis is down | Medium | Medium | Medium | Fail-closed concurrency control (§4) |
| T7 | Prompt injection in user queries | High | **High** | **High** | Prompt injection detection (§5) |
| T8 | No role-based access control (RBAC) | Medium | **High** | Medium | Add RBAC with roles/permissions (§6) |
| T9 | No audit trail for sensitive operations | Medium | Medium | Medium | Add audit logging middleware (§7) |
| T10 | Docker container running as root | High | Medium | Medium | Non-root user in Dockerfile (§9) |
| T11 | `.env` / secrets in Docker build context | High | **High** | **High** | .dockerignore (§9) |

### Data Flow Diagram (Security Boundary)
```
[Internet] → [TLS] → [FastAPI]
                        ├── /auth/signup  → DB (bcrypt hashing)
                        ├── /auth/login   → JWT (RS256 signing)
                        ├── /query/*      → [RateLimit] → [Concurrency] → [Auth/RBAC] → [Audit] → [RAG Pipeline]
                        ├── /ingest/*     → [RateLimit] → [Auth/RBAC] → [Audit] → [Storage]
                        ├── /ws/*         → [JWT Auth] → [Audit] → [WebSocket Handler]
                        ├── /health       → [No Auth]  → Health Check
                        └── /             → [No Auth]  → Root
```

---

## 2. RS256 JWT Migration

### Problem
The current implementation uses **HS256** (symmetric HMAC-SHA256) for JWT signing:
- Same key signs AND verifies tokens
- Secret key appears with a hardcoded fallback in `backend/core/security.py`
- Any service that knows the secret can forge tokens

### Solution
Migrate to **RS256** (asymmetric RSA-SHA256):
- Private key signs tokens (held by auth service only)
- Public key verifies tokens (can be distributed to microservices)
- Use `cryptography` library for RSA key generation
- Auto-generate key pair on first run if not provided

### Key Management
- Private key stored as `JWT_PRIVATE_KEY` in `.env` (base64-encoded PEM)
- Public key stored as `JWT_PUBLIC_KEY` in `.env` (base64-encoded PEM)
- Generation script: `make jwt-keys` or `python -c "from backend.core.security import generate_rsa_keypair; print(generate_rsa_keypair())"`

### Migration Steps
1. Set `JWT_PRIVATE_KEY` and `JWT_PUBLIC_KEY` in `.env`
2. Auth router decodes with `PUBLIC_KEY` and `RS256` algorithm
3. Old HS256 tokens will be rejected — all users must re-authenticate
4. Monitor for token validation errors during cutover

---

## 3. Rate Limiting Hardening

### Changes
- **Redis authentication**: Read `REDIS_PASSWORD` from settings, pass to `redis.Redis()`
- **Redis TLS**: Optional `REDIS_USE_SSL` setting
- **User-based limiting**: Rate limit by `(user_id, ip)` instead of just IP
- **Fail-closed fallback**: When Redis is down, reject requests with 503 instead of allowing unlimited traffic
- **Separate limits per endpoint**: Auth endpoints get stricter limits (5 req/min)

---

## 4. Request Concurrency Control

### New Module: `backend/api/middleware/concurrency.py`

Implements a **semaphore-based concurrency limiter** to prevent resource exhaustion:
- Configurable max concurrent requests per user (default: 5)
- Configurable global max concurrent requests (default: 50)
- Uses Redis for distributed semaphore when available
- Falls back to in-process `asyncio.Semaphore` for single-instance deployments
- Returns 429 when limit exceeded

---

## 5. Prompt Injection Detection

### New Module: `backend/core/prompt_injection.py`

Detects common prompt injection patterns before they reach the LLM:
- **Role-play bypass**: "Ignore previous instructions", "You are now...", "System prompt..."
- **Direct injection**: "Say yes if...", "Repeat exactly...", embedded instructions
- **Delimiter confusion**: Base64-encoded prompts, hex-encoded strings
- **Context override**: Trying to override system messages
- **XSS in prompts**: `<script>` tags, markdown injection
- Uses regex-based detection with configurable sensitivity
- Returns structured response with threat severity and matched pattern
- Integrated into `llm_client.py` before sending to the LLM

---

## 6. RBAC (Role-Based Access Control)

### New Module: `backend/core/rbac.py`

### Roles
| Role | Permissions |
|------|-------------|
| `admin` | Full access to all endpoints, user management |
| `editor` | Can query RAG, ingest documents, view own history |
| `viewer` | Can query RAG only, view own history |
| `auditor` | Can view audit logs only |

### Implementation
- `Role` enum with associated permissions
- `require_role(*roles)` dependency for FastAPI routes
- `require_permission(permission)` dependency for fine-grained control
- User model gains `role` field (default: `"viewer"`)
- JWT tokens include `role` claim
- Backward compatible — missing `role` defaults to `viewer`

---

## 7. Audit Logging

### New Module: `backend/core/audit.py`

### Events Logged
| Event | Description | Data |
|-------|-------------|------|
| `user.login` | User login | email, ip, user_agent, timestamp |
| `user.signup` | New registration | email, tenant_id, timestamp |
| `query.execute` | RAG query execution | query_hash (not raw text), user_uuid, session_id |
| `ingest.upload` | Document ingestion | filename, size, user_uuid, tenant_id |
| `auth.failure` | Authentication failure | email, ip, reason |
| `rate_limit.hit` | Rate limit exceeded | ip, user_id, endpoint |
| `prompt_injection` | Injection attempt detected | query_hash, threat_level |
| `rbac.denied` | Authorization failure | user_uuid, role, required_role, endpoint |

### Storage
- Primary: Append to structured JSONL file (`audit_logs/`)
- Secondary: Redis stream (ephemeral, for real-time monitoring)
- Rotation: Log files rotate at 100MB, keep last 10 rotations
- No PII in logs (emails are hashed, queries are hashed)

---

## 8. WebSocket Authentication

### Current State
WebSocket `/ws/{session_id}` has **no authentication** — any client can connect.

### Solution
- Require JWT token as query parameter: `/ws/{session_id}?token=<jwt>`
- Validate token on connection before upgrading
- Reject with 403 if token is invalid/expired
- Maintain RBAC for WebSocket events

---

## 9. Docker Hardening

### Dockerfile Changes
- Add non-root `app` user (UID 1000)
- Add `HEALTHCHECK` instruction
- Use `--no-cache-dir` for pip
- Set `--no-install-recommends` for apt
- Use `COPY` with specific paths instead of `COPY . .`

### Docker Compose Changes
- Remove hardcoded passwords
- Use secrets or env vars for all credentials
- Add Redis password configuration
- Add network isolation (internal networks)

### `.dockerignore`
- `.env`, `.git/`, `__pycache__/`, `*.egg-info/`, `node_modules/`
- `test_data/`, `eval_results/`, `audit_logs/`, `chroma_data/`
- `scratch/`, `docs/`, `frontend/`, `frontend-old/`

---

## 10. Security Tests

| Test File | Coverage |
|-----------|----------|
| `test_security_rbac.py` | Role/permission decorators, JWT role extraction, access control |
| `test_security_audit.py` | Audit event creation, JSONL persistence, Redis stream |
| `test_security_prompt_injection.py` | All injection patterns, bypass attempts, false positive rate |
| `test_security_rate_limit.py` | Redis auth, user-based limiting, fail-closed behavior |

---

## 11. CI Integration

Added to `.github/workflows/main.yml`:
```yaml
security-tests:
  runs-on: ubuntu-latest
  steps:
    - name: Run security unit tests
      run: PYTHONPATH=. pytest backend/tests/unit/test_security_*.py -v
```

---

## 12. Migration Plan

### Phase 6a — Core Security (Immediate)
1. Deploy RS256 key pair generation script
2. Update `.env` with `JWT_PRIVATE_KEY` and `JWT_PUBLIC_KEY`
3. Deploy new `security.py` with RS256
4. All existing sessions invalidated — users re-authenticate
5. Monitor auth failure rates

### Phase 6b — Middleware (Same deploy)
1. Deploy hardened rate limit middleware
2. Deploy concurrency control middleware
3. Register in main.py

### Phase 6c — Detection & Authorization (Same deploy)
1. Deploy prompt injection detection
2. Deploy RBAC module
3. Add `role` column to User model
4. Run migration to set default roles

### Phase 6d — Audit & Hardening (Same deploy)
1. Deploy audit logging
2. Deploy WebSocket auth
3. Deploy Docker hardening

## 13. Rollback Plan

### Step 1: Revert code
```bash
git revert <security-commit-hash>
git push origin main
```

### Step 2: If HS256 tokens are needed
- Revert `JWT_ALGORITHM` in config back to `HS256`
- Revert `security.py` to use `HS256` and `SECRET_KEY`

### Step 3: If Docker changes need revert
```bash
git checkout HEAD~1 -- infra/docker/Dockerfile.api
git checkout HEAD~1 -- docker-compose.yml
git checkout HEAD~1 -- .dockerignore
```

### Step 4: Verify
```bash
make test-security
curl http://localhost:8000/health
```

## 14. Operational Runbook

### Monitoring
- **Auth failures**: Alert if >10% of requests fail auth in 5min window
- **Rate limit hits**: Alert if rate limit hit rate >100/min
- **Prompt injection detections**: Pager if >5 detected in 1min
- **RBAC denials**: Log all denials, investigate spikes

### Key Rotation
```bash
# Generate new RS256 key pair
python -c "from backend.core.security import generate_rsa_keypair; print(generate_rsa_keypair())"

# Update .env with new keys
# Old tokens will be invalid — staged rollout recommended
```

### Emergency Procedures
1. **JWT compromise**: `git revert` to HS256, rotate all credentials, force re-auth
2. **Rate limit bypass**: Increase Redis password complexity, restrict network access
3. **Prompt injection outbreak**: Disable LLM endpoint temporarily, analyze patterns
4. **Audit log disk full**: Implement log rotation, S3 archival, alert at 80% capacity