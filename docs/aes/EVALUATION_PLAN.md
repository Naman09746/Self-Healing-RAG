# Autonomous Experiment Scientist (AES) - Evaluation Plan

## 1. Evaluation Hierarchy
AES evaluates RAG performance across a four-tier metric hierarchy:

1. **Answer Quality (RAGAS & Deterministic Heuristics):**
   - *Faithfulness:* Are all assertions in the generated answer directly supported by the retrieved contexts?
   - *Answer Relevance:* Does the answer directly address the user query without extraneous padding?
   - *Context Precision:* Are the retrieved documents relevant, and are relevant chunks ranked at the top?
   - *Context Recall:* Do the retrieved chunks contain all the information required to produce the reference answer?
   - *Heuristic Fallback:* Exact keyword overlap, rouge-like token F1, and sentence inclusion when running offline or in lightweight test environments.

2. **System Latency:**
   - Mean latency per query.
   - p50, p90, p95, and p99 latency per query (in milliseconds).
   - Component-level latency breakdown (Routing, Retrieval, Grading, Generation, Evaluation).

3. **Cost & Resource Efficiency:**
   - Input token count, output token count, and simulated cost based on model pricing tariffs.
   - Self-healing retry count (e.g. how many times retrieval or generation had to re-execute).

4. **Statistical Reliability:**
   - Sample variance and standard deviation across queries.
   - 95% Bootstrap Confidence Intervals (bias-corrected accelerated or percentile).
   - Paired Wilcoxon signed-rank test p-value relative to the default baseline.

## 2. Benchmark Datasets

### 2.1 Golden Dataset (Dataset V1)
- 20 rigorously curated evaluation samples stored in `data/eval/dataset_v1.json`.
- Spans 4 distinct query types:
  - *Factual single-hop:* Direct entity and definition lookup.
  - *Multi-hop reasoning:* Synthesizing facts across multiple retrieved chunks.
  - *Adversarial / Out-of-domain:* Queries with no relevant answer in the corpus, verifying negative rejection.
  - *Ambiguous / High-complexity:* Queries requiring self-healing query reformulation.

### 2.2 Candidate Dataset (Dataset V2)
- Synthetic question-answer pairs generated from corpus documents.
- Stored in `data/eval/dataset_v2_candidates.json` with metadata:
  ```json
  {
    "id": "cand_001",
    "query": "...",
    "ground_truth": "...",
    "source_doc": "...",
    "status": "candidate",
    "human_reviewed": false
  }
  ```
- Evaluated alongside Dataset V1 only when explicitly specified, preventing untested synthetic data from degrading core benchmark integrity.
