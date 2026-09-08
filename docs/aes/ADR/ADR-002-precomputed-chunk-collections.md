# ADR-002: Pre-computed Chunk Collections for Indexing Experiments

## Status
Accepted

## Context
Evaluating chunking parameters (`chunk_size`, `chunk_overlap`) typically requires wiping or re-indexing the entire document corpus into ChromaDB. During an experimentation campaign consisting of 10-20 trials, re-indexing on every trial would incur prohibitive latency (several minutes per trial) and introduce race conditions against the production vector store.

## Decision
We pre-compute discrete chunking variants into dedicated ChromaDB collections during an initial one-off offline script:
- `rag_collection_c500_o50`: chunk size 500, overlap 50
- `rag_collection_c700_o100`: chunk size 700, overlap 100
- `rag_collection_c1500_o300`: chunk size 1500, overlap 300

When an experiment requests a specific chunking configuration, the deterministic engine maps the request directly to the appropriate collection name (`collection_name` setting override).

## Consequences
- **Positive:** Zero re-indexing overhead during trial runs; trials execute in seconds rather than minutes; production collection remains completely untouched.
- **Negative:** Search space for chunk size is restricted to pre-indexed discrete points rather than arbitrary continuous intervals.
