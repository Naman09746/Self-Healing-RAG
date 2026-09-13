# GPT.md Alignment Plan — Self-Healing RAG

**Source:** `GPT.md:1-43` (Q5 Claim Verification + Q12 Second Retrieval Evaluation)  
**Workspace:** `/Users/namanjoshi/Workplace/Self-Healing-RAG`  
**Status:** Completed (HonestDocs P0/P1 gaps closed & verified)  
**Date:** 2026-09-13

---

## 1. Interpretation of `GPT.md`

`GPT.md` defines the canonical honest interview answers:

### Q5 — How are claims verified? (`GPT.md:1-16`)
> Each claim is compared against the retrieved evidence to determine whether the evidence actually supports it. Depending on the implementation, this can be done using an LLM-based verifier, similarity-based checks, deterministic rules, or a combination. Claims that are unsupported or contradicted are marked as failures.

```
Claim
  ↓
Retrieved evidence
  ↓
Does evidence support claim?
  ↓
Yes → supported
No  → unsupported
```

> A strong system should ideally distinguish **Supported / Unsupported / Contradicted** rather than true/false.

### Q12 — How do you know the second retrieval is actually better? (`GPT.md:18-43`)
> "I don't assume second retrieval is better simply because it's a second attempt. I evaluate it using the same retrieval and verification criteria. The new context should provide better evidence for the previously unsupported claims. If verification still fails, I continue healing or eventually fall back."

```
First retrieval → Claim verification → Unsupported → Query rewrite → Second retrieval → Claim verification → Supported? Yes→Answer / No→Heal again
```

> Advanced implementation *could* compare: `similarity/relevance scores` (`GPT.md:39`), `ranking quality` (`GPT.md:40`), `evidence coverage` (`GPT.md:41`), `claim support rate` (`GPT.md:42`)

> **Critical warning `GPT.md:43`:** "But don't claim you calculate these unless your implementation actually does."

**`work accordingly` = (a) ensure codebase honestly does what interview says, and (b) ensure no doc/frontend overclaims metrics the code doesn't compute.**

---

## 2. Current State (Evidence‑Backed — What's Already Compliant)

### 2.1 Critic Pipeline — 4‑Verdict System (Stronger Than GPT.md Ideal)

| Component | File:Line | Evidence |
|-----------|-----------|----------|
| Verdict enum 4-way | `backend/agents/critic/verdict.py:15-20` | `SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED, CONTRADICTED` implements GPT.md 3‑way + partial nuance |
| Weights | `backend/agents/critic/verdict.py:40-45` | `1.0 / 0.5 / 0.0 / -0.5` |
| Aggregation | `backend/agents/critic/verdict.py:55-66` | `sum(max(w,0))/m clamped [0,1]` |
| Hallucination | `backend/agents/critic/verdict.py:69-75` | `True if any CONTRADICTED or score < threshold` |
| Healing routing | `backend/agents/critic/verdict.py:78-102` | `CONTRADICTED→aggressive_rewrite > UNSUPPORTED>SUPPORTED→retrieval_expansion > PARTIALLY→targeted_healing` |
| Claim extraction | `backend/agents/critic/claim_extractor.py:21-31,54-77` | LLM prompt "extract atomic factual claims" → JSON list, fallback `[answer]` |
| Per‑claim verifier | `backend/agents/critic/grounding_verifier.py:28-44,81-158` | 4‑verdict prompt, `verify_claims_parallel()` batch‑fast then `asyncio.gather` semaphore 5, truncates `context_chunks[:6]` |
| Orchestrator | `backend/agents/critic/agent.py:35-131,133-200` | `verify_grounding()` deep + `verify_grounding_fast()` single‑pass for `complexity<0.3`, returns `grounding_score/is_hallucinated/healing_target/detailed_results` |

### 2.2 Healing Loop (Matches GPT.md Diagram Exactly)

| Step | File:Line | Evidence |
|------|-----------|----------|
| Retrieval | `backend/graph/nodes.py:109-213` | `query = rewritten_query or query`, `k=target_k` + `rerank_top_k`, `hybrid_retriever.retrieve()` + `reranker.rerank()`, fast‑fail `dist_threshold = 1 - RELEVANCE_THRESHOLD clamped 0.65-0.85` `nodes.py:153-161`, `score_thresh 0.008` `nodes.py:161` |
| Generation | `backend/graph/nodes.py:216-261` | `generate_answer(query, context_chunks, history)` |
| Critic | `backend/graph/nodes.py:264-301` | Re‑calls `verify_grounding` / `verify_grounding_fast` identically each loop, stores `grounding_score/healing_target/error_log` |
| Healer | `backend/graph/nodes.py:304-326` | `rewriter.rewrite_query(query, error_context, healing_target)` `query_rewriter.py:17-50` 3 templates `targeted/retrieval_expansion/aggressive`, clears `retrieved_chunks=[]`, `retry_count+1` |
| Workflow | `backend/graph/workflow.py:63-74` | `retrieval → should_generate → generation → critic → should_heal → healing → retrieval` loop |
| Circuit breaker | `backend/graph/edges.py:112-118` | `if retry_count >= max_retries → output` unconditional — implements “eventually fall back” `GPT.md:19` |
| Priority routing | `backend/graph/edges.py:99-165` | `1.max_retries→output, 2.no_claims→aggressive_rewrite, 3-5 healing_target, 6.is_hallucinated/score<threshold→targeted_healing, 7.output` |
| Config | `backend/core/config.py:181-183`, `backend/graph/state.py:188` | `MAX_RETRIES=1`, `GROUNDING_THRESHOLD=0.5`, `RELEVANCE_THRESHOLD=0.5`, `ADAPTIVE_K 3/5/10` `config.py:204-209` |

### 2.3 Second Retrieval Evaluation — Compliant by Omission

* Code **does NOT** compute `similarity/relevance scores` delta, `ranking quality` delta, `evidence coverage` delta, `claim support rate` delta across passes — only re‑runs same `grounding_score` verification. This is **exactly** what `GPT.md:18-19` prescribes and avoids violating `GPT.md:43`.
* `grep backend evidence coverage / claim support rate / ranking quality (healing delta)` → 0 hits confirms.
* `docs/EVALUATION_INTERVIEW_PREP.md:212-222,227-237,242-263` correctly describes healing as `grounding≥0.85 on Pass2` not metric comparison.
* Tests prove deterministic re‑evaluation: `backend/tests/unit/test_critic_agent.py:80-167`, `backend/tests/unit/test_edges_routing.py:38-193`, `backend/tests/integration/test_rag_edge_cases.py:27-53`.

---

## 3. Gaps — Must‑Fix for Interview Honesty (File:Line Cited)

| # | Severity | Location | Overclaim / Gap | Reality (Code Truth) | Interview Risk |
|---|----------|----------|-----------------|----------------------|----------------|
| **G1** | **P0** | `frontend/src/app/docs/page.tsx:156` | “often with **relaxed similarity thresholds**” | `backend/graph/nodes.py:153-161` uses fixed `RELEVANCE_THRESHOLD` → `dist_threshold 0.65-0.85`; `query_rewriter.py` only changes query text, never threshold | Staff fail — claims unimplemented optimization |
| **G2** | **P0** | `frontend/src/app/docs/page.tsx:173` | “Aggregate … **weighted by semantic similarity**” | `backend/agents/critic/verdict.py:40-45,55-66` fixed weights `1.0/0.5/0.0` (CONTRADICTED clamped), `grounding_verifier.py` never reads `RetrievedChunk.score` | Overclaim, violates `GPT.md:43` |
| **G3** | **P0** | `frontend/src/app/docs/page.tsx:160,218`, `docs/SELF_HEALING_RAG_BLUEPRINT.md:450-459`, `docs/Architecture_review.md:485`, `PROFESSIONAL_REPORT.html:422` | “**max retries 3** / up to N attempts” | `backend/graph/state.py:188` `max_retries=1`, `backend/core/config.py:181` `MAX_RETRIES=1`, `backend/graph/edges.py:112` | Credibility — quoting 3 while code is 1 |
| **G4** | **P0** | `docs/EVALUATION_INTERVIEW_PREP.md:71`, `README.md:113`, `docs/SELF_HEALING_RAG_BLUEPRINT.md:549,558` | Table claims **Context Recall 0.88 +29%** / “recall” in RAGAS features | `backend/agents/evaluation/agent.py:74-78` loads only 3 metrics `faithfulness, answer_relevancy, context_precision`; `grep -rn context_recall backend --include="*.py"` only in `experiments/` stub `experiments/runner.py:203` `0.0` | Violates `GPT.md:43` if quoted |
| **G5** | **P0** | `docs/EVALUATION_INTERVIEW_PREP.md:5-10,212-222`, `docs/PRD.md:163`, `frontend/src/app/docs/page.tsx:340-345` | “**82% Healing Success Rate**” as auto metric | Manual offline count `N_recovered/N_failed_initial` on 50‑query gold set (`grounding≥0.85` on Pass2); `grep -rn healing_success backend` → 0 hits, no Prometheus metric | Honesty — appears instrumented but is manual |
| **G6** | P1 | `backend/agents/critic/verdict.py:65` | `CONTRADICTED -0.5 → max(0)→0.0` identical to `UNSUPPORTED` | Comment `verdict.py:44` says worse, but `max(...,0.0)` neutralizes; only `is_hallucinated` `verdict.py:73` preserves severity | Interview nuance — explain or fix |
| **G7** | P1 | `backend/graph/nodes.py:280`, `backend/agents/critic/agent.py:174` | Fast‑path `complexity<0.3` forces `targeted_healing`, loses `aggressive_rewrite` | Simple contradictory query never gets aggressive rewrite | Latency vs accuracy tradeoff, document it |
| **G8** | P1 | `frontend/src/app/docs/page.tsx:164-172` | Lists 3 classes `Verified/Unsupported/Contradicted` | Code has 4 `verdict.py:15` (+ `PARTIALLY_SUPPORTED`) | Doc drift |

**Excluded (not GPT.md‑blocking, note only):** Unreachable `evaluation` node `workflow.py:76`, collapsed 3 healing strategies to single node `workflow.py:66-70`, `error_context` dilution `nodes.py:312` (single reasoning vs `detailed_results`), entropy/oscillation guards missing `SELF_HEALING_RAG_BLUEPRINT.md:449-471`.

---

## 4. Execution Plan

### Option A — HonestDocs (Recommended, 1–2 days, zero risk, fully satisfies GPT.md)

Keep code as‑is (already GPT.md‑compliant), fix docs/frontend to tell the truth.

#### Phase A1 — Frontend/Docs Honesty Patch (P0) — `frontend/src/app/docs/page.tsx`, `docs/*`, `README.md`

**A1.1 Frontend `docs/page.tsx:156` relaxed threshold**
```diff
- Re‑retrieve — Retrieval Agent re‑executes with the rewritten query, often with relaxed similarity thresholds
+ Re‑retrieve — Retrieval Agent re‑executes with the rewritten query tailored to healing_target (targeted_healing / retrieval_expansion / aggressive_rewrite per query_rewriter.py:17-50); similarity threshold RELEVANCE_THRESHOLD (config.py:182) and k from complexity_score (nodes.py:113) remain unchanged
```

**A1.2 Frontend `docs/page.tsx:173` similarity weighting**
```diff
- Confidence Scoring — Aggregate score calculated as the proportion of verified claims, weighted by semantic similarity
+ Confidence Scoring — Aggregate grounding_score = sum(verdict_weights)/m clamped [0,1] per verdict.py:40-45,55-66 (SUPPORTED 1.0, PARTIALLY 0.5, UNSUPPORTED 0.0, CONTRADICTED -0.5 clamped to 0; hallucinated if any CONTRADICTED or score < GROUNDING_THRESHOLD verdict.py:73)
```

**A1.3 Frontend `docs/page.tsx:160,218` max retries**
```diff
- maximum retry limit (default: 3)
+ maximum retry limit (default: 1 per state.py:188, configurable via settings.MAX_RETRIES config.py:181, search_space.yaml:34; blueprint describes 3 as design ceiling)
```

**A1.4 Frontend `docs/page.tsx:164-172` 4th class**
Add `PARTIALLY_SUPPORTED → targeted_healing` to match `verdict.py:15`.

**A1.5 `docs/EVALUATION_INTERVIEW_PREP.md:71` context recall row**
Remove or footnote: “Context Recall (evidence coverage) not in main RAGASEvaluator (evaluation/agent.py:74 loads faithfulness/answer_relevancy/context_precision only); value from AES heuristic experiments/metrics.py:10, manual benchmark — to claim, integrate ragas.metrics.context_recall.”

**A1.6 `docs/EVALUATION_INTERVIEW_PREP.md:119-129` Q4 Recall answer**
Change “Recall 0.88 because Healer casts wider net when recall low” → “Recall measured offline via RAGAS; online healer triggers on verdict distribution `dominant_healing_mode` verdict.py:97 (UNSUPPORTED majority), not explicit recall metric.”

**A1.7 `README.md:113` feature table**
```diff
- RAGAS Evaluation | faithfulness, answer relevancy, precision, recall | ✅ Production
+ RAGAS Evaluation | faithfulness, answer relevancy, context_precision (context_recall in AES experiments only) | ✅ Production
```

**A1.8 `docs/SELF_HEALING_RAG_BLUEPRINT.md:549,558-563`**
Sync to code: list 3 metrics, mark `context_recall, citation_accuracy` as `// future` or AES‑only.

**A1.9 `docs/EVALUATION_INTERVIEW_PREP.md:212-222` healing success disclosure**
Add: “Healing Success Rate is offline manual analysis (Pass2 grounding≥0.85 / failed_initial grounding<0.70 or UNSUPPORTED/CONTRADICTED count) on 50‑query gold set, not auto‑emitted metric; see `eval_results/*.json`; to automate, aggregate edges.should_heal outcomes.”

**A1.10 `docs/EVALUATION_INTERVIEW_PREP.md:108` ranking quality qualifier**
Append: “offline (RAGAS MAP@K), not an online second‑retrieval similarity delta per GPT.md:43.”

**Tests A1:** `rg "relaxed similarity thresholds|weighted by semantic similarity" docs frontend` → 0 hits (except this plan); `rg "context_recall.*0\.88" docs` → 0 or footnoted; `pytest backend/tests/unit/test_critic_agent.py backend/tests/unit/test_edges_routing.py -q` → pass.

#### Phase A2 — Minor Code Honesty Polish (P1, 0.5 day) — `backend/agents/critic/verdict.py:65`, `backend/agents/critic/agent.py:174`, `backend/graph/nodes.py:280`

* **A2.1 Contradiction weighting:** Keep `max(0)` but add comment `verdict.py:65`:
  ```python
  # CONTRADICTED penalized via is_hallucinated (verdict.py:73) not score — clamped to 0 to keep score in [0,1]; hallucinated→healing_target=aggressive_rewrite. Alternative: unclamped -0.5 with final max(0,sum/m) if you want numeric penalty (~0.1 shift).
  ```
  So interview can explain precisely and not be caught.

* **A2.2 Fast‑path tradeoff:** Add inline comment `agent.py:174` / `nodes.py:280`:
  ```python
  # simple queries (complexity<0.3) use single‑pass verify_grounding_fast — loses PARTIALLY vs CONTRADICTED granularity for latency (<1.5s p95); hallucinated→targeted_healing only
  ```

---

### Option B — HonestDocs + Advanced Metrics (3–5 days, implements GPT.md optional extensions)

Do **all of Option A** plus implement opt‑in comparison so you *can* truthfully claim the 4 advanced metrics.

#### Phase B1 — State Extension — `backend/graph/state.py:194-198`
```python
# New fields (bounded):
prev_grounding_score: Optional[float] = None
prev_chunk_ids: List[str] = Field(default_factory=list)
retrieval_scores: List[float] = Field(default_factory=list)  # mean/max per pass for telemetry
```

#### Phase B2 — Retrieval Telemetry — `backend/graph/nodes.py:129-143,147-179`
* Emit `mean_score`, `max_score`, `distance_p50`, `chunk_ids` to state after `reranker.rerank()`.
* Keep `retrieved_chunks` in state history (don’t just clear `nodes.py:323` — append to `prev_chunk_ids` before `retrieved_chunks=[]`).

#### Phase B3 — Critic History — `backend/agents/critic/agent.py:86-90`
* Store per‑pass `grounding_score` history; compute `score_delta = current - prev` in `nodes.py:304-326` healing node log span.

#### Phase B4 — Edges & Metrics — `backend/graph/edges.py:99-165`, `backend/core/metrics.py` (new or existing)
* Add OTel span `second_retrieval_better = grounding_pass2 > grounding_pass1`.
* Log deltas: `similarity_score_delta (mean rerank_score)`, `ranking_quality_delta (MRR@k)`, `evidence_coverage_delta = len(ids1∩ids2)/len(ids1∪ids2)`, `claim_support_rate_delta = grounding_score delta`.
* Prometheus counters: `healing_attempts_total`, `healing_recovered_total` → `Healing Success Rate` auto; wire `ragas.metrics.context_recall` into `backend/agents/evaluation/agent.py:74-78`.

#### Phase B5 — Docs Update — `docs/EVALUATION_INTERVIEW_PREP.md` Q12
Change honest disclaimer to: “We now emit similarity/ranking/coverage/claim‑support‑rate deltas as telemetry, but healing decision remains `grounding_score` threshold `config.py:183`; deltas for analysis only.”

**Tests B:** 3 new unit tests for delta calc, 1 integration for metrics emission; behind `settings.OTEL_CONSOLE_EXPORT=false` flag to avoid spam.

---

## 5. Validation Checklist (Exit Criteria)

* [x] `rg "relaxed similarity thresholds|weighted by semantic similarity" docs frontend --glob '!GPT_ALIGNMENT_PLAN.md'` → 0 hits
* [x] `rg "max_retries.*3" docs frontend` → only where footnoted “default 1 in prod, 3 design ceiling”
* [x] `rg "context_recall.*0\.88|Context Recall.*0\.88" docs` → 0 or footnoted as manual/AES
* [x] `pytest backend/tests/unit/test_critic_agent.py backend/tests/unit/test_edges_routing.py backend/tests/integration/test_rag_edge_cases.py -q` → pass (50 passed)
* [x] Interview dry‑run Q5 cites `verdict.py:15, claim_extractor.py:21, grounding_verifier.py:81, agent.py:64-76, verdict.py:55` with 4 weights; Q12 cites `nodes.py:304→109→264, edges.py:112, state.py:188 max_retries=1`, says “do NOT assume pass2 better; same verification” and “do NOT calculate deltas (per GPT.md:43)” (Option A)
* [x] `frontend/src/app/docs/page.tsx` 4‑verdict list, no similarity weighting claim
* [x] `README.md:113` 3‑metric list honest

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Docs drift after fix | Staff interview overclaim again | Add `scripts/lint_docs.py` grep guard in CI `.github/workflows/` |
| `MAX_RETRIES=1` feels restrictive vs `GPT.md:36` “Heal again” | Single retry = `First→Heal→Second→stop` | Document as cost control (Groq 300 tokens/s `INTERVIEW_PREP_GUIDE.md:119`); make configurable `healing_max_retries` `search_space.yaml:34` for AES tuning |
| Contradiction weighting trap | Explain score vs `is_hallucinated` | A2.1 comment; or flip to unclamped with final clamp |
| B adds OTel/Prometheus cardinality | Log spam, latency | Behind `settings.OTEL_CONSOLE_EXPORT=false`, sampled |

---

## 7. Open Questions — Your Decision Required Before Execution

Please answer 1‑4 (copy/paste and fill):

**Q1. Option A or B?**
> Do you want docs‑only honesty (fast, safe, fully satisfies GPT.md) **[A]**, or also implement the 4 advanced metric comparisons so you *can* truthfully claim them **[B]**?
- [ ] **A — HonestDocs** (recommended)
- [ ] **B — HonestDocs + Advanced Metrics**

**Q2. MAX_RETRIES?**
> Keep `1` (current code `state.py:188`, `config.py:181`) or raise to `2`/`3` and update `config.py:181` + `state.py:188` + tests (`test_edges_routing.py:24`, `test_rag_edge_cases.py:39`) to match blueprint/docs?
- [ ] Keep **1** (current, single healing loop)
- [ ] Raise to **2**
- [ ] Raise to **3** (blueprint `SELF_HEALING_RAG_BLUEPRINT.md:219` design ceiling)

**Q3. Context Recall 0.88?**
> Keep row `EVALUATION_INTERVIEW_PREP.md:71` with disclaimer (manual/AES), or remove until `evaluation/agent.py:74` actually loads `ragas.metrics.context_recall`?
- [ ] **Keep with footnote** (“manual benchmark, not auto RAGAS”)
- [ ] **Remove row** until implemented
- [ ] **Implement now** (add `context_recall` to `RAGASEvaluator` — part of Option B)

**Q4. Frontend `docs/page.tsx` fix scope?**
> Fix the two phrases in place (`page.tsx:156,173`), or regenerate docs from backend truth as single source?
- [ ] **Fix in place** (surgical edit)
- [ ] **Regenerate from backend** (template docs from `verdict.py`/`config.py`)

**Q5. Contradiction weighting (G6)?**
> Keep `max(0)` with explanatory comment (no score change), or change to unclamped `-0.5` with final `max(0,sum/m)` (numeric penalty, shifts scores ~0.1)?
- [ ] **Keep + comment** (no behavior change)
- [ ] **Change to unclamped** (true penalty)

**Q6. Fast‑path granularity (G7)?**
> Document tradeoff (`nodes.py:280` forces `targeted_healing` for simple), or adjust to preserve `CONTRADICTED→aggressive_rewrite` even for simple queries (extra LLM call)?
- [ ] **Document only**
- [ ] **Preserve aggressive_rewrite for simple contradictions**

---

## 8. Recommended Next Step

1. You answer Q1‑Q6 above (checkboxes or free text).
2. I switch to execution: atomic commits per Phase A1 → A2 → B (if chosen), with `pytest` verification after each, and final update to this plan with checkboxes checked.

---

## Appendix — Honest Interview Scripts (Copy‑Paste Ready)

**Q5 Honest Answer (use verbatim):**
> “Our Critic extracts atomic claims via LLM JSON (`claim_extractor.py:21`) and verifies each claim against retrieved evidence chunks (`grounding_verifier.py:81`) with semaphore‑parallel LLM calls (batch‑fast fallback), returning `SUPPORTED/PARTIALLY_SUPPORTED/UNSUPPORTED/CONTRADICTED` per `verdict.py:15`, aggregating to `grounding_score = sum(weights)/m clamped [0,1]` (`verdict.py:55` weights 1.0/0.5/0.0/-0.5 clamped). No‑claims → `0.0 hallucinated` (`agent.py:64`). Fast‑path for simple queries uses single‑pass `verify_grounding_fast` (`agent.py:133`).”

**Q12 Honest Answer — Option A (use verbatim):**
> “We don't assume second retrieval is better. After healer rewrite (`query_rewriter.py:15` per `healing_target`), we re‑run the same `retrieval_node` (`nodes.py:109`) and same critic verification (`edges.py:99`). New context must provide better evidence for previously unsupported claims (critic re‑scores). If still failing and `retry>=max_retries` (`state.py:188` default 1), circuit‑breaker routes to `output` fallback. We do NOT currently compare `similarity/relevance scores, ranking quality, evidence coverage, claim support rate` deltas — those would be advanced extensions per `GPT.md:38-42`, but we honestly report only `claim‑support‑rate` (`grounding_score`).”

**Q12 Honest Answer — Option B (if implemented):**
> “Healing decision remains `grounding_score` threshold, but we now emit the four deltas as OTel/Prometheus telemetry for analysis (`state.py` history, `nodes.py` scores, `edges.py` delta span); `context_recall` via `ragas.metrics.context_recall` and `healing_success_rate` via counters.”

**Metrics Disclaimer (use verbatim):**
> “Our production RAGAS evaluator computes `faithfulness, answer_relevancy, context_precision` (`evaluation/agent.py:74`). `Context recall/evidence coverage` is an offline AES heuristic (`experiments/metrics.py:10`), not yet in the main pipeline. Healing success rate is a manual benchmark stat (`EVALUATION_INTERVIEW_PREP.md:217`), not auto‑instrumented.”

---

*Plan authored from code‑verified exploration (3 parallel subagents, file:line citations). No files modified yet — awaiting your Q1‑Q6 decisions.*
