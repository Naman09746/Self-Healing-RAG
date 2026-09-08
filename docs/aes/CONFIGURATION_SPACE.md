# Autonomous Experiment Scientist (AES) - Configuration Space Specification

## 1. Parameter Definitions & Constraints
The configuration search space is formally declared in YAML and validated by Pydantic. It spans retrieval, reranking, routing, chunking, and self-healing parameters:

| Parameter Name | Data Type | Default | Bounds / Categories | Step | Safe Clamping Rule |
|---|---|---|---|---|---|
| `top_k` | `int` | `5` | `[1, 20]` | `1` | `max(1, min(20, round(val)))` |
| `hybrid_search_alpha` | `float` | `0.5` | `[0.0, 1.0]` | `0.05` | `max(0.0, min(1.0, float(val)))` |
| `rerank_threshold` | `float` | `0.0` | `[0.0, 1.0]` | `0.05` | `max(0.0, min(1.0, float(val)))` |
| `routing_confidence_threshold`| `float`| `0.6` | `[0.3, 0.95]` | `0.05` | `max(0.3, min(0.95, float(val)))` |
| `healing_max_retries` | `int` | `2` | `[0, 5]` | `1` | `max(0, min(5, round(val)))` |
| `grading_threshold` | `float` | `0.5` | `[0.2, 0.9]` | `0.05` | `max(0.2, min(0.9, float(val)))` |
| `chunk_size` | `int` | `700` | `[500, 700, 1500]` | Discrete | Routed to pre-computed collections |
| `chunk_overlap` | `int` | `100` | `[50, 100, 300]` | Discrete | Paired with `chunk_size` |

## 2. Pre-computed Collection Mapping
To ensure zero latency and zero data-loss risk during re-indexing trials:
- `(chunk_size=500, chunk_overlap=50)` $\rightarrow$ `collection_name="rag_collection_c500_o50"`
- `(chunk_size=700, chunk_overlap=100)` $\rightarrow$ `collection_name="rag_collection_c700_o100"`
- `(chunk_size=1500, chunk_overlap=300)` $\rightarrow$ `collection_name="rag_collection_c1500_o300"`

If an experiment specifies a chunk size outside these discrete variants, the engine clamps to the nearest available pre-computed collection and logs a warning.
