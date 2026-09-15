# ROLE

Act as a **Principal AI/ML Engineer, RAG Architect, LLM Systems Engineer, and Production Infrastructure Reviewer** with deep expertise in:

* Advanced RAG architectures
* Hybrid retrieval
* Dense + sparse retrieval
* Chunking and document parsing
* Reranking
* Query rewriting
* Multi-agent RAG
* Self-correcting / self-healing RAG
* Hallucination detection
* NLI / claim verification
* LLM evaluation
* Vector databases
* PostgreSQL + pgvector
* BM25 / full-text search
* Knowledge graphs
* Context engineering
* LLM inference optimization
* Streaming architectures
* Distributed systems
* Caching
* Observability
* Production reliability
* Security
* Cost optimization

I am giving you my **complete existing Self-Healing RAG codebase**.

Your job is NOT to simply praise it or rewrite everything.

Your job is to **deeply audit the system as it actually exists**, understand every stage of the pipeline, identify architectural weaknesses, compare it against what a highly mature/production-grade RAG system should look like, and then recommend the smallest set of changes that would make it substantially better.

---

# PRIMARY OBJECTIVE

Analyze my existing implementation and answer:

> **"If this RAG system were reviewed by a senior RAG/LLM systems engineer at a top AI company, what would they criticize, what would they change, and why?"**

I want the system to become:

* More correct
* More robust
* More retrieval-accurate
* More resistant to hallucinations
* Better at complex queries
* Better at multi-hop questions
* Better at long documents
* Better at code/JSON/structured documents
* Lower latency
* Lower memory usage
* Lower LLM/API cost
* More observable
* More deterministic where appropriate
* Easier to test
* Easier to maintain
* Production-ready

Do NOT optimize only for benchmarks.

Optimize for **real-world correctness + reliability + engineering quality**.

---

# IMPORTANT RULE

## FIRST UNDERSTAND THE CURRENT SYSTEM

Do NOT immediately propose a new architecture.

First reconstruct my actual architecture from the code.

Trace the complete flow:

```text
Document
   ↓
Ingestion
   ↓
Parsing
   ↓
Cleaning / Normalization
   ↓
Chunking
   ↓
Metadata
   ↓
Embedding
   ↓
Indexing
   ↓
Query
   ↓
Query Processing
   ↓
Retrieval
   ↓
Hybrid Retrieval
   ↓
Fusion
   ↓
Reranking
   ↓
Context Construction
   ↓
LLM Generation
   ↓
Claim Verification / Critic
   ↓
Healing / Query Rewrite
   ↓
Retry / Re-retrieval
   ↓
Final Answer
   ↓
Evaluation / Observability
```

The actual implementation may differ.

If it differs, **document the real architecture rather than assuming the diagram above is correct.**

---

# PHASE 1 — RECONSTRUCT THE CURRENT ARCHITECTURE

Inspect the entire repository.

Identify:

1. Entry points
2. API endpoints
3. Ingestion pipeline
4. Document loaders
5. Text extraction
6. Cleaning
7. Chunking
8. Metadata generation
9. Embedding generation
10. Vector storage
11. Sparse retrieval
12. Dense retrieval
13. Hybrid retrieval
14. Reciprocal Rank Fusion
15. Reranking
16. Query rewriting
17. Critic
18. Healer
19. Circuit breaker
20. Context packing
21. LLM calls
22. Streaming
23. Caching
24. Redis usage
25. PostgreSQL usage
26. Evaluation
27. Metrics
28. Logging
29. Tracing
30. Error handling
31. Rate limiting
32. Concurrency control
33. Tests

Create a **real architecture diagram in text** based on the code.

Example:

```text
User
 ↓
FastAPI
 ↓
Query Router
 ↓
Hybrid Retriever
 ├── pgvector
 └── PostgreSQL FTS
 ↓
RRF
 ↓
Reranker
 ↓
Context Packer
 ↓
LLM
 ↓
Claim Critic
 ├── PASS
 └── FAIL → Query Healer → Retriever
```

But only show components that actually exist.

---

# PHASE 2 — TRACE ONE QUERY END-TO-END

Pick one realistic query and follow it through the entire implementation.

For every stage explain:

* Input
* Output
* Transformation
* Data structure
* Important parameters
* Failure modes
* Latency
* Cost
* What can go wrong

For example:

```text
User Query
↓
Query Normalization
↓
Query Rewrite
↓
Dense Retrieval
↓
Sparse Retrieval
↓
RRF
↓
Reranking
↓
Top-K
↓
Context Packing
↓
LLM
↓
Claim Extraction
↓
NLI Verification
↓
Healing
```

I want you to identify the **exact boundaries where information can be lost or corrupted.**

---

# PHASE 3 — CHUNKING AUDIT

This is extremely important.

Do NOT treat chunking as:

```python
RecursiveCharacterTextSplitter(...)
```

and move on.

Analyze whether my chunking strategy is actually appropriate.

Evaluate:

### 1. Chunk size

Is the current chunk size appropriate?

Consider:

* token count rather than characters
* embedding model limits
* LLM context window
* retrieval precision
* retrieval recall
* semantic completeness

### 2. Chunk overlap

Determine whether overlap is:

* too small
* too large
* unnecessary
* incorrectly applied

Explain why.

### 3. Semantic boundaries

Determine whether chunks respect:

* paragraphs
* headings
* sections
* lists
* tables
* code blocks
* JSON
* Markdown
* HTML
* PDFs
* documentation
* FAQs

### 4. Parent-child retrieval

Evaluate whether the system should use:

```text
Parent Document
      ↓
Child Chunks
```

where retrieval happens on child chunks but the parent/section context is returned to the LLM.

### 5. Hierarchical chunking

Determine whether hierarchical retrieval would improve complex documents.

### 6. Contextual chunking

Evaluate whether chunks should contain additional context such as:

```text
Document: Employee Handbook
Section: Leave Policy
Subsection: Sick Leave

[actual chunk]
```

instead of embedding only the raw chunk.

### 7. Tables

Evaluate how tables are handled.

Do NOT assume tables can safely be treated as normal text.

### 8. Code and structured data

Evaluate handling of:

* Python
* JSON
* YAML
* SQL
* Markdown
* configuration files

Check whether chunks can break syntax or destroy relationships.

### 9. Chunk deduplication

Check whether overlapping chunks create duplicate retrieval results.

### 10. Chunk IDs

Check whether chunk IDs allow:

* tracing
* versioning
* updates
* deletion
* debugging

### 11. Document versioning

Check whether changed documents can invalidate old chunks.

### 12. Retrieval-aware chunking

Evaluate whether chunking is optimized for the actual retrieval strategy.

Give me a concrete recommendation such as:

```text
Current:
500 characters + 50 overlap

Recommended:
semantic section chunks
~250–500 tokens
parent-child retrieval
metadata-aware embeddings
```

But only recommend values after reasoning about my actual corpus and architecture.

---

# PHASE 4 — RETRIEVAL AUDIT

Analyze dense retrieval.

Check:

* embedding model
* embedding dimensions
* similarity metric
* normalization
* top-K
* filtering
* metadata filtering
* index configuration
* HNSW parameters
* recall
* latency
* concurrency

Then analyze sparse retrieval.

Check:

* BM25 / PostgreSQL FTS
* tokenization
* stemming
* stopwords
* phrase matching
* exact identifiers
* numbers
* product names
* technical terminology

Then analyze hybrid retrieval.

Evaluate:

```text
Dense Retrieval
       +
Sparse Retrieval
       ↓
Fusion
```

Check whether RRF is implemented correctly.

If using:

```text
RRF(k=60)
```

explain whether this value makes sense or whether it should be tuned.

---

# PHASE 5 — RETRIEVAL FAILURE VS GENERATION FAILURE

This is critical.

Determine whether the current system can distinguish:

### Retrieval failure

The correct evidence was never retrieved.

Example:

```text
Question:
"What is the refund period?"

Retrieved:
pricing information
security information
account limits

Correct refund policy:
not retrieved
```

This is retrieval failure.

### Generation / grounding failure

Correct evidence was retrieved but the LLM generated an unsupported answer.

Example:

```text
Retrieved:
"Refunds are available within 30 days."

LLM:
"Refunds are available within 60 days."
```

This is a generation/grounding failure.

Determine whether my architecture detects this correctly.

If not, design a robust mechanism.

---

# PHASE 6 — RERANKING AUDIT

Evaluate:

* Is reranking necessary?
* Where is it placed?
* What model is used?
* How many candidates enter reranking?
* How many chunks leave reranking?
* Is reranking too expensive?
* Can it be skipped for simple queries?
* Is cross-encoder reranking appropriate?
* Would late interaction / ColBERT-style retrieval help?
* Is the reranker score being interpreted correctly?

Do NOT recommend expensive reranking everywhere.

Design a sensible strategy.

---

# PHASE 7 — QUERY UNDERSTANDING

Evaluate whether the system correctly handles:

### Simple queries

```text
"What is the monthly price?"
```

### Complex queries

```text
"Compare the Professional and Enterprise plans and explain which is better for a 100-person company."
```

### Multi-hop queries

```text
"What is the cancellation policy for customers using annual billing?"
```

### Ambiguous queries

```text
"How much does it cost?"
```

### Follow-up queries

```text
"What about Enterprise?"
```

### Conversational queries

```text
"Does that apply to international customers?"
```

Determine whether I need:

* query rewriting
* query decomposition
* multi-query retrieval
* HyDE
* hypothetical answer generation
* query routing
* metadata filtering
* conversation-aware rewriting

Do NOT recommend every technique.

Choose only what solves an actual problem in my system.

---

# PHASE 8 — MULTI-HOP / COMPLEX QUERY HANDLING

This is a major area.

Determine whether the current architecture can answer questions requiring multiple pieces of evidence.

Example:

```text
Question:
"Which plan supports SSO and costs less than $100 per month?"
```

This may require:

```text
Retrieve pricing
+
Retrieve feature support
+
Combine evidence
```

Evaluate whether I need:

```text
Query decomposition
        ↓
Sub-question 1
Sub-question 2
        ↓
Parallel retrieval
        ↓
Evidence aggregation
        ↓
Answer synthesis
```

Explain whether this should be added.

---

# PHASE 9 — CONTEXT ENGINEERING

Audit the exact context sent to the LLM.

Check:

* number of chunks
* token budget
* ordering
* duplicate chunks
* neighboring chunks
* metadata
* citations
* source attribution
* lost-in-the-middle problem
* irrelevant context
* context compression
* context prioritization

Determine whether:

```text
Top 10 chunks
```

is actually better than:

```text
Top 5 high-quality chunks
```

Do not assume more context is better.

---

# PHASE 10 — CONTEXT PACKING

Inspect my context packing algorithm carefully.

Determine whether it:

* respects token limits
* preserves semantic boundaries
* preserves Markdown
* preserves code blocks
* preserves JSON
* prevents truncation
* removes duplicates
* preserves document hierarchy
* prioritizes high-value evidence

Identify any edge cases.

---

# PHASE 11 — HALLUCINATION DETECTION

Audit the Critic.

Determine:

* How claims are extracted
* Whether claims are atomic
* How claims map to evidence
* NLI model
* NLI thresholds
* SUPPORTED / PARTIAL / UNSUPPORTED / CONTRADICTED logic
* false positives
* false negatives
* numerical claims
* negation
* dates
* comparisons
* multi-sentence claims

Example:

```text
Evidence:
"Refunds are available within 30 days."

Answer:
"Customers can request refunds within 60 days."
```

The critic should identify this as contradiction.

Evaluate whether my implementation actually can.

---

# PHASE 12 — SELF-HEALING LOOP AUDIT

Analyze the complete feedback loop.

Current conceptual design:

```text
Retrieve
 ↓
Generate
 ↓
Critic
 ↓
If bad
 ↓
Heal
 ↓
Rewrite query
 ↓
Retrieve again
```

Evaluate:

* termination conditions
* maximum retries
* retry explosion
* cost
* latency
* repeated bad queries
* circuit breaker
* confidence thresholds
* fallback behavior

Design a better control policy if necessary.

---

# PHASE 13 — FAST PATH

Evaluate whether simple queries should bypass expensive stages.

Example:

```text
Simple factual query
↓
Retrieve
↓
Generate
```

versus:

```text
Complex query
↓
Query decomposition
↓
Hybrid retrieval
↓
Reranking
↓
Generation
↓
Claim verification
↓
Healing
```

Determine whether a query complexity router would meaningfully improve latency and cost.

---

# PHASE 14 — CACHING

Audit caching.

Determine whether I should cache:

* embeddings
* retrieval results
* reranking results
* rewritten queries
* final responses

Check cache invalidation.

Especially analyze:

```text
Document updated
↓
Old retrieval cache
↓
Incorrect answer
```

Design safe cache keys involving relevant document/version information.

---

# PHASE 15 — DATABASE / PGVECTOR AUDIT

Review PostgreSQL and pgvector architecture.

Check:

* schema
* indexes
* HNSW
* vector dimensions
* distance metric
* metadata filtering
* FTS indexes
* connection pooling
* concurrency
* transactions
* migrations
* document versioning
* deletion
* stale embeddings

Identify bottlenecks.

---

# PHASE 16 — REDIS AUDIT

Review Redis usage.

Check:

* caching
* distributed locks
* rate limiting
* concurrency control
* TTL
* key design
* race conditions
* stale keys
* failure behavior

Determine whether Redis is being used appropriately.

---

# PHASE 17 — COST OPTIMIZATION

Calculate where unnecessary LLM/API calls happen.

Analyze:

```text
Embedding cost
Retrieval cost
Reranking cost
LLM generation cost
Critic cost
Healing cost
Retry cost
```

Identify opportunities for:

* caching
* batching
* fast path
* smaller models
* local models
* conditional evaluation
* parallelism

---

# PHASE 18 — LATENCY OPTIMIZATION

Break down latency:

```text
Query processing
+
Embedding
+
Dense retrieval
+
Sparse retrieval
+
RRF
+
Reranking
+
LLM
+
Critic
+
Healing
```

Identify serial operations that could be parallelized.

For example:

```text
Dense Retrieval ─────┐
                     ├──> Fusion
Sparse Retrieval ────┘
```

instead of:

```text
Dense → Sparse → Fusion
```

But only recommend parallelization when safe.

---

# PHASE 19 — OBSERVABILITY

Determine whether I can answer:

> "Why did the system give this answer?"

For every request, I should ideally be able to trace:

```text
query_id
document_ids
chunk_ids
retrieval scores
reranker scores
final context
LLM model
prompt/version
critic decision
healing attempt
final answer
latency
token usage
errors
```

Identify missing observability.

---

# PHASE 20 — EVALUATION

Audit my evaluation strategy.

Do not rely only on:

* answer relevancy
* context precision

Evaluate whether I need:

* context recall
* faithfulness
* answer correctness
* retrieval recall@K
* precision@K
* MRR
* nDCG
* reranker effectiveness
* hallucination rate
* healing success rate
* latency
* token cost

Design a realistic evaluation dataset.

Include:

1. Easy factual questions
2. Retrieval-heavy questions
3. Multi-hop questions
4. Ambiguous questions
5. Numerical questions
6. Negative questions
7. Unanswerable questions
8. Contradictory documents
9. Duplicate documents
10. Updated documents
11. Long documents
12. Code/JSON questions

---

# PHASE 21 — ADVERSARIAL TESTING

Try to break my RAG system.

Test conceptually for:

* hallucination
* prompt injection
* malicious documents
* conflicting sources
* stale documents
* duplicate documents
* misleading chunks
* irrelevant high-similarity chunks
* long-context distraction
* numerical errors
* negation errors
* outdated policies
* ambiguous queries
* empty retrieval
* retrieval timeout
* LLM timeout
* embedding failure
* database failure

Tell me exactly how the architecture should behave in each case.

---

# PHASE 22 — SECURITY AUDIT

Review:

* prompt injection
* indirect prompt injection
* document poisoning
* tenant isolation
* authorization
* rate limiting
* API abuse
* secret management
* SSRF
* malicious uploaded documents
* unsafe tool usage

Do not assume retrieval content is trusted.

---

# PHASE 23 — COMPARE AGAINST MATURE RAG ARCHITECTURES

Now compare my system conceptually against modern production-grade RAG patterns used in serious LLM systems.

Do NOT claim that you have access to proprietary internal ChatGPT architecture.

Instead compare against **publicly documented and broadly accepted advanced RAG patterns**, such as:

* hybrid search
* multi-stage retrieval
* reranking
* query routing
* query decomposition
* parent-child retrieval
* contextual retrieval
* semantic chunking
* hierarchical retrieval
* knowledge graph augmentation
* agentic retrieval
* adaptive retrieval
* corrective RAG
* self-reflective RAG
* citation verification
* claim-level grounding
* context compression
* retrieval evaluation
* observability
* caching
* production reliability

For every technique answer:

```text
Technique
↓
What problem does it solve?
↓
Does my system already solve it?
↓
If yes, how well?
↓
If no, do I actually need it?
↓
Expected benefit
↓
Engineering complexity
↓
Cost
```

Do NOT add complexity merely because it is fashionable.

---

# PHASE 24 — IDENTIFY OVERENGINEERING

This is equally important.

Tell me what I have implemented that may be unnecessarily complex.

For example:

* unnecessary agents
* unnecessary LLM calls
* unnecessary retries
* excessive chunking complexity
* expensive reranking
* unnecessary databases
* unnecessary abstractions
* redundant validation

If a simpler deterministic solution is better, say so.

---

# PHASE 25 — PRODUCE THE IDEAL ARCHITECTURE

After understanding and auditing the current implementation, design the recommended architecture.

Separate it into:

### Ingestion

```text
Documents
 ↓
Parser
 ↓
Structure Detection
 ↓
Semantic Chunking
 ↓
Metadata
 ↓
Deduplication
 ↓
Embedding
 ↓
Index
```

### Query

```text
User Query
 ↓
Query Router
 ↓
Query Rewrite / Decomposition if needed
 ↓
Parallel Hybrid Retrieval
 ↓
Fusion
 ↓
Reranking
 ↓
Context Construction
 ↓
LLM
 ↓
Claim Verification
 ↓
Healing if necessary
 ↓
Final Answer
```

But adapt this architecture to my actual system.

---

# PHASE 26 — PRIORITIZED IMPROVEMENTS

Do NOT give me 100 random recommendations.

Rank improvements:

## P0 — Critical correctness issues

Things that can cause wrong answers.

## P1 — High-value improvements

Major improvements to retrieval, grounding, reliability.

## P2 — Performance improvements

Latency, memory, cost.

## P3 — Nice-to-have improvements

Advanced techniques with smaller benefit.

For every recommendation give:

```text
Problem:
Current implementation:
Why it is problematic:
Recommended change:
Expected benefit:
Complexity:
Files affected:
```

---

# PHASE 27 — CODE-LEVEL RECOMMENDATIONS

For every important recommendation identify:

```text
File:
Class/function:
Current behavior:
Recommended behavior:
```

Do not invent file names.

Use the actual repository.

If you recommend modifying code, show a focused code patch or implementation example.

Do NOT rewrite the entire repository unless absolutely necessary.

Prefer:

```text
small change → measurable improvement
```

over:

```text
complete rewrite
```

---

# PHASE 28 — BEFORE/AFTER ARCHITECTURE

Show:

### CURRENT

```text
[actual architecture]
```

### RECOMMENDED

```text
[improved architecture]
```

Then explicitly show:

```text
Removed:
Added:
Changed:
Kept:
```

---

# PHASE 29 — FINAL VERDICT

Give the system a score from 0–10 for:

| Area                    | Score |
| ----------------------- | ----: |
| Ingestion               |       |
| Chunking                |       |
| Retrieval               |       |
| Hybrid Search           |       |
| Reranking               |       |
| Query Understanding     |       |
| Context Engineering     |       |
| Generation              |       |
| Hallucination Detection |       |
| Self-Healing            |       |
| Evaluation              |       |
| Observability           |       |
| Security                |       |
| Reliability             |       |
| Performance             |       |
| Production Readiness    |       |

Then give:

### Biggest 5 weaknesses

### Biggest 5 strengths

### Top 10 changes I should actually implement

### What NOT to change

### Expected final architecture

---

# VERY IMPORTANT CONSTRAINTS

1. **Do not hallucinate features that aren't present in the code.**
2. **Do not assume my README accurately describes the implementation. Verify it against source code.**
3. **Do not recommend technologies simply because they are popular.**
4. **Do not replace PostgreSQL/pgvector just because another vector DB exists. Explain the actual tradeoff.**
5. **Do not recommend agents when deterministic code would be better.**
6. **Do not recommend more LLM calls unless they provide measurable value.**
7. **Prioritize correctness over architectural novelty.**
8. **Prioritize retrieval quality before blaming the LLM.**
9. **Treat chunking as a first-class architectural problem.**
10. **Treat retrieved context as the boundary between retrieval failure and generation failure.**
11. **Consider latency and cost for every additional stage.**
12. **Do not blindly optimize for benchmark scores.**
13. **Consider production failure modes.**
14. **Do not rewrite working components without evidence.**
15. **Use actual code paths and actual configuration values in your analysis.**

---

# MOST IMPORTANT QUESTION

At the end, answer this:

> **If you were responsible for taking this exact RAG system from its current state to a genuinely strong production-grade RAG system, what would you change first, second, third, and why?**

Give me a **concrete engineering roadmap**, not generic RAG advice.

The goal is not to make the architecture look impressive.

The goal is:

> **Given the same data, queries, infrastructure, and LLM, make the system retrieve the right evidence more consistently, generate fewer unsupported claims, heal intelligently when retrieval fails, and do all of this with the lowest reasonable latency and cost.**
