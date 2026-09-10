#!/usr/bin/env python3
"""
Live RAG Query Test Script
Run an end-to-end live query through the Self-Healing RAG pipeline.

Usage:
    uv run python scripts/test_live_query.py
    uv run python scripts/test_live_query.py --query "What is Self-Healing RAG?"
    uv run python scripts/test_live_query.py --ingest "Self-Healing RAG is an autonomous 7-agent pipeline designed to eliminate hallucinations using LangGraph and PostgreSQL pgvector." --query "How does Self-Healing RAG prevent hallucinations?"
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.core.config import settings
from backend.core.logging import setup_logging, get_logger
from backend.core.observability import setup_otel_tracing
from backend.graph.container import ServiceContainer
from backend.graph.workflow import create_rag_graph
from backend.graph.runner import run_rag_pipeline

setup_logging()
logger = get_logger("live_test")


async def main():
    parser = argparse.ArgumentParser(description="Run a real live query through the Self-Healing RAG pipeline.")
    parser.add_argument(
        "--query",
        type=str,
        default="What is the Self-Healing RAG pipeline and what vector store does it use?",
        help="Query to ask the RAG pipeline",
    )
    parser.add_argument(
        "--ingest",
        type=str,
        default=(
            "The Self-Healing RAG pipeline is an enterprise-grade multi-agent knowledge system. "
            "It is orchestrated using LangGraph with 7 specialized agents: Intake, Planner, Hybrid Retriever, "
            "Generator, Critic, Healer, and Output. For vector storage, it uses PostgreSQL pgvector with HNSW indexing, "
            "providing full ACID consistency and zero multi-worker lock contention. It detects hallucinations using atomic "
            "claim extraction and automatically heals ungrounded claims via a query rewriting loop."
        ),
        help="Sample text to ingest before querying",
    )
    parser.add_argument("--skip-ingest", action="store_true", help="Skip document ingestion")
    parser.add_argument("--tenant", type=str, default="default", help="Tenant ID")

    args = parser.parse_args()

    print("\n" + "=" * 75)
    print("🧠 SELF-HEALING RAG — LIVE QUERY TEST RUNNER")
    print("=" * 75)
    print(f"📦 Active Vector Store Provider: {getattr(settings, 'VECTOR_STORE_PROVIDER', 'pgvector')}")
    print(f"📦 Active Session Store Provider: {getattr(settings, 'SESSION_STORE_PROVIDER', 'pg')}")
    print(f"📦 Active Sparse Provider:        {getattr(settings, 'SPARSE_PROVIDER', 'pg_tsvector')}")
    print(f"📦 Active Reranker Provider:      {getattr(settings, 'RERANKER_PROVIDER', 'none')}")
    print(f"🤖 LLM Provider / Model:         {settings.LLM_PROVIDER} ({settings.MODEL_NAME})")
    print("-" * 75)

    # 1. Initialize OpenTelemetry & Services
    setup_otel_tracing()
    print("\n⏳ Initializing service container and LangGraph...")
    deps = ServiceContainer.build()
    graph = create_rag_graph(deps)
    print("✅ Service container and LangGraph state machine ready!")

    # 2. Ingest Sample Document if requested
    if not args.skip_ingest and args.ingest:
        print("\n📥 Ingesting sample context into vector & sparse storage...")
        t0_ingest = time.time()
        try:
            chunks = [args.ingest]
            metadatas = [{"document_id": "doc_live_demo_001", "chunk_index": 0, "title": "Live Demo Context"}]
            ids = ["chunk_live_demo_001"]

            # Add to vector store
            deps.vector_store.add_chunks(chunks=chunks, metadatas=metadatas, ids=ids, tenant_id=args.tenant)
            
            # Add to sparse store if available
            if hasattr(deps, "sparse_store") and deps.sparse_store:
                deps.sparse_store.index(documents=chunks, metadata=metadatas, ids=ids, tenant_id=args.tenant)

            ingest_ms = (time.time() - t0_ingest) * 1000
            print(f"✅ Ingestion successful ({ingest_ms:.1f}ms) — 1 document chunk indexed!")
        except Exception as e:
            print(f"⚠️ Ingestion note: {e}")

    # 3. Execute Live Pipeline
    print(f"\n🔍 Executing live query: \"{args.query}\"")
    print("─" * 75)
    
    t0 = time.time()
    try:
        result = await run_rag_pipeline(
            graph=graph,
            deps=deps,
            query=args.query,
            tenant_id=args.tenant,
            skip_cache=True,
            skip_websocket=True,
        )
        total_ms = (time.time() - t0) * 1000

        print("\n🎉 PIPELINE EXECUTION COMPLETED!")
        print("=" * 75)
        print(f"⏱️  Total Latency:         {total_ms:.1f} ms")
        print(f"📊 Status:                {result.get('status', 'SUCCESS')}")
        print(f"🛡️  Grounding Score:       {result.get('grounding_score', 'N/A')}")
        print(f"🔄 Retry Count:           {result.get('retry_count', 0)}")
        chunks_val = result.get("chunks_retrieved", 0)
        chunks_count = len(chunks_val) if isinstance(chunks_val, list) else chunks_val
        print(f"📚 Chunks Retrieved:      {chunks_count}")
        print("-" * 75)
        print("💬 GENERATED ANSWER:")
        print(result.get("answer") or result.get("generation_result", {}).get("answer", "(No answer generated)"))
        print("=" * 75 + "\n")

    except Exception as e:
        print(f"\n❌ Pipeline execution error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
