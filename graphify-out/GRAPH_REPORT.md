# Graph Report - /Users/namanjoshi/Workplace/Self-Healing-AI-Agent  (2026-05-15)

## Corpus Check
- Corpus is ~16,214 words - fits in a single context window. You may not need a graph.

## Summary
- 188 nodes · 170 edges · 44 communities (36 shown, 8 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 22 edges (avg confidence: 0.66)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Data Ingestion & Loading|Data Ingestion & Loading]]
- [[_COMMUNITY_Graph State & Nodes|Graph State & Nodes]]
- [[_COMMUNITY_Frontend UI Components|Frontend UI Components]]
- [[_COMMUNITY_Generation & LLM Client|Generation & LLM Client]]
- [[_COMMUNITY_Critic & Verification|Critic & Verification]]
- [[_COMMUNITY_Configuration & Vector Storage|Configuration & Vector Storage]]
- [[_COMMUNITY_Session Memory|Session Memory]]
- [[_COMMUNITY_API Query Endpoints|API Query Endpoints]]
- [[_COMMUNITY_Query Caching|Query Caching]]
- [[_COMMUNITY_API Tests|API Tests]]
- [[_COMMUNITY_Logging|Logging]]
- [[_COMMUNITY_Telemetry|Telemetry]]
- [[_COMMUNITY_Evaluation Agent|Evaluation Agent]]
- [[_COMMUNITY_API Core|API Core]]
- [[_COMMUNITY_Rate Limiting|Rate Limiting]]
- [[_COMMUNITY_Graph Edges|Graph Edges]]
- [[_COMMUNITY_Graph Workflow|Graph Workflow]]
- [[_COMMUNITY_Ingest Endpoint|Ingest Endpoint]]
- [[_COMMUNITY_Loaders Init|Loaders Init]]
- [[_COMMUNITY_LLM Client Rationale|LLM Client Rationale]]

## God Nodes (most connected - your core abstractions)
1. `LLMClient` - 11 edges
2. `ChromaStore` - 8 edges
3. `GroundingVerifier` - 6 edges
4. `ClaimExtractor` - 6 edges
5. `Chunker` - 5 edges
6. `IngestionPipeline` - 5 edges
7. `SessionMemory` - 5 edges
8. `CriticAgent` - 5 edges
9. `BaseLoader` - 4 edges
10. `PDFLoader` - 4 edges

## Surprising Connections (you probably didn't know these)
- `IngestionPipeline` --uses--> `ChromaStore`  [INFERRED]
  backend/ingestion/pipeline.py → backend/storage/vector/chroma.py
- `EvaluationAgent` --uses--> `RAGState`  [INFERRED]
  backend/agents/evaluation/agent.py → backend/graph/state.py
- `GroundingVerifier` --uses--> `LLMClient`  [INFERRED]
  backend/agents/critic/grounding_verifier.py → backend/agents/generation/llm_client.py
- `ClaimExtractor` --uses--> `LLMClient`  [INFERRED]
  backend/agents/critic/claim_extractor.py → backend/agents/generation/llm_client.py
- `IngestionPipeline` --uses--> `Chunker`  [INFERRED]
  backend/ingestion/pipeline.py → backend/ingestion/chunker.py

## Communities (44 total, 8 thin omitted)

### Community 0 - "Data Ingestion & Loading"
Cohesion: 0.13
Nodes (9): ABC, Chunker, Split text into chunks., IngestionPipeline, Ingest a single file into the vector store., BaseLoader, DocumentLoader, PDFLoader (+1 more)

### Community 1 - "Graph State & Nodes"
Cohesion: 0.11
Nodes (17): critic_node(), evaluation_node(), generation_node(), healing_node(), intake_node(), output_node(), Heal the pipeline by rewriting the query and incrementing retries., Evaluate the final generated response. (+9 more)

### Community 2 - "Frontend UI Components"
Cohesion: 0.17
Nodes (7): queryRAG(), QueryResponse, uploadFile(), ChatMessage, Props, Props, RAGState

### Community 3 - "Generation & LLM Client"
Cohesion: 0.15
Nodes (6): GenerationAgent, Generate an answer based on the provided context., LLMClient, Production-grade LLM client with circuit breaking and retries., QueryRewriter, Rewrite the query to improve retrieval performance.

### Community 4 - "Critic & Verification"
Cohesion: 0.15
Nodes (6): CriticAgent, Deep verification using atomic claim extraction., ClaimExtractor, Extract atomic factual claims from the answer., GroundingVerifier, Verify a single claim against the context.

### Community 5 - "Configuration & Vector Storage"
Cohesion: 0.17
Nodes (6): BaseSettings, Settings, ChromaStore, Add chunks to the collection., Query the collection., Delete all chunks associated with a document.

### Community 6 - "Session Memory"
Cohesion: 0.22
Nodes (4): Add a message to the session history., Retrieve the last N messages from the session history., Clear session history., SessionMemory

### Community 7 - "API Query Endpoints"
Cohesion: 0.28
Nodes (7): BaseModel, Execute the full RAG pipeline via LangGraph., run_rag_pipeline(), query_rag(), QueryRequest, QueryResponse, Multi-agent RAG query (Phase 3).

### Community 8 - "Query Caching"
Cohesion: 0.29
Nodes (3): QueryCache, Check if a similar query has been answered recently., Cache a query and its answer.

### Community 9 - "API Tests"
Cohesion: 0.33
Nodes (4): Test the health check endpoint., Test the root endpoint., test_health_check(), test_root()

### Community 10 - "Logging"
Cohesion: 0.4
Nodes (4): get_logger(), Get a structured logger instance., Configure structured logging using structlog., setup_logging()

### Community 11 - "Telemetry"
Cohesion: 0.4
Nodes (4): get_tracer(), Configure OpenTelemetry for tracing., Get a tracer instance., setup_telemetry()

## Knowledge Gaps
- **42 isolated node(s):** `ChatMessage`, `Props`, `Props`, `QueryResponse`, `Split text into chunks.` (+37 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RAGState` connect `Graph State & Nodes` to `Evaluation Agent`, `API Query Endpoints`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Why does `LLMClient` connect `Generation & LLM Client` to `Critic & Verification`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Why does `ChromaStore` connect `Configuration & Vector Storage` to `Data Ingestion & Loading`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `LLMClient` (e.g. with `QueryRewriter` and `GroundingVerifier`) actually correct?**
  _`LLMClient` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `ChromaStore` (e.g. with `IngestionPipeline` and `Settings`) actually correct?**
  _`ChromaStore` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `GroundingVerifier` (e.g. with `LLMClient` and `CriticAgent`) actually correct?**
  _`GroundingVerifier` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `ClaimExtractor` (e.g. with `CriticAgent` and `LLMClient`) actually correct?**
  _`ClaimExtractor` has 3 INFERRED edges - model-reasoned connections that need verification._