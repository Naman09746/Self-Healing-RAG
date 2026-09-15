"""Retrieval diagnostics — Phase 2 correctness verification.

Reports:
 - documents / vector_chunks / sparse_chunks counts
 - chunks by tenant
 - embedding model / expected dim / actual DB vector dim / query vector dim
 - HNSW index existence + ef_search
 - distance/score distributions for test queries
 - stage-by-stage top-k: dense, sparse, graph, RRF, reranker

Usage:
    python -m backend.evaluation.diagnostics --retrieval --tenant default
    python -m backend.evaluation.diagnostics --retrieval --query "stipend Acme" --k 5

Does NOT modify thresholds or data. For re-ingestion use --reingest flag (Phase 2).
"""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path
from typing import Any

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.storage.vector.embeddings import get_embedding_provider, _resolve_model_dim

# Neon DNS workaround: local resolver (192.168.31.1) intermittently fails for
# ep-cold-hill-b35d4g9r.c-4.ap-southeast-1.aws.neon.tech (CNAME). Patch getaddrinfo
# to fallback to hardcoded IPs resolved via 8.8.8.8 (dig shows 52.76.246.190 etc).
# Keeps original hostname for SNI/TLS but uses IP for TCP.
import socket as _socket

_orig_getaddrinfo = _socket.getaddrinfo
_NEON_FALLBACK_IPS = ["52.76.246.190", "52.76.212.156", "3.0.27.201"]

def _patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    try:
        return _orig_getaddrinfo(host, port, family, type, proto, flags)
    except _socket.gaierror as e:
        if host and "neon.tech" in host:
            # Return fallback IPs for any neon.tech host
            # Preserve caller family if specified, else return IPv4
            res = []
            for ip in _NEON_FALLBACK_IPS:
                try:
                    # Try to return both families as original would
                    res.append((_socket.AF_INET, _socket.SOCK_STREAM, 6, "", (ip, port)))
                except Exception:
                    pass
            if res:
                return res
        raise

try:
    _socket.getaddrinfo = _patched_getaddrinfo
except Exception:
    pass

logger = get_logger(__name__)


async def _get_db_counts(tenant: str) -> dict[str, Any]:
    """Fetch counts without importing heavy stores."""
    result: dict[str, Any] = {"error": None}
    try:
        from sqlalchemy import text

        # Use shared engine if available, else create isolated
        try:
            from backend.storage.db.session import engine as shared_engine

            engine = shared_engine
        except Exception:
            from sqlalchemy.ext.asyncio import create_async_engine
            from sqlalchemy.pool import NullPool

            engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, echo=False)

        async with engine.begin() as conn:
            # documents
            try:
                r = await conn.execute(text("SELECT COUNT(*) FROM documents"))
                result["documents"] = int(r.scalar() or 0)
            except Exception as e:
                result["documents"] = f"error: {e}"
            # vector_chunks total
            try:
                r = await conn.execute(text("SELECT COUNT(*) FROM vector_chunks"))
                result["vector_chunks_total"] = int(r.scalar() or 0)
            except Exception as e:
                result["vector_chunks_total"] = f"error: {e}"
            # by tenant
            try:
                r = await conn.execute(text("SELECT tenant_id, COUNT(*) FROM vector_chunks GROUP BY tenant_id"))
                result["vector_by_tenant"] = {row[0]: int(row[1]) for row in r.fetchall()}
            except Exception as e:
                result["vector_by_tenant"] = f"error: {e}"
            # sparse
            try:
                r = await conn.execute(text("SELECT COUNT(*) FROM sparse_chunks"))
                result["sparse_chunks_total"] = int(r.scalar() or 0)
            except Exception as e:
                result["sparse_chunks_total"] = f"error: {e}"
            try:
                r = await conn.execute(text("SELECT tenant_id, COUNT(*) FROM sparse_chunks GROUP BY tenant_id"))
                result["sparse_by_tenant"] = {row[0]: int(row[1]) for row in r.fetchall()}
            except Exception as e:
                result["sparse_by_tenant"] = f"error: {e}"
            # actual DB vector dim via pg_attribute
            try:
                r = await conn.execute(
                    text(
                        """
                        SELECT format_type(atttypid, atttypmod)
                        FROM pg_attribute
                        WHERE attrelid = 'vector_chunks'::regclass AND attname = 'embedding'
                        """
                    )
                )
                row = r.fetchone()
                result["db_vector_type"] = str(row[0]) if row else "unknown"
                # parse vector(1536) -> 1536
                if row and "vector(" in str(row[0]):
                    try:
                        result["db_vector_dim"] = int(str(row[0]).split("(")[1].split(")")[0])
                    except Exception:
                        result["db_vector_dim"] = None
                else:
                    result["db_vector_dim"] = None
            except Exception as e:
                result["db_vector_type"] = f"error: {e}"
                result["db_vector_dim"] = None
            # HNSW index
            try:
                r = await conn.execute(
                    text(
                        """
                        SELECT indexname, indexdef
                        FROM pg_indexes
                        WHERE tablename = 'vector_chunks' AND indexdef ILIKE '%hnsw%'
                        """
                    )
                )
                rows = r.fetchall()
                result["hnsw_indexes"] = [{"name": row[0], "def": row[1]} for row in rows] if rows else []
            except Exception as e:
                result["hnsw_indexes"] = f"error: {e}"
            # sparse GIN
            try:
                r = await conn.execute(
                    text(
                        """
                        SELECT indexname, indexdef
                        FROM pg_indexes
                        WHERE tablename = 'sparse_chunks' AND indexdef ILIKE '%gin%'
                        """
                    )
                )
                rows = r.fetchall()
                result["gin_indexes"] = [{"name": row[0], "def": row[1]} for row in rows] if rows else []
            except Exception as e:
                result["gin_indexes"] = f"error: {e}"
            # tenant filtered count
            try:
                r = await conn.execute(text("SELECT COUNT(*) FROM vector_chunks WHERE tenant_id = :tid"), {"tid": tenant})
                result["vector_tenant_count"] = int(r.scalar() or 0)
            except Exception as e:
                result["vector_tenant_count"] = f"error: {e}"

        # Do not dispose shared_engine; only dispose if we created one
        try:
            if "shared_engine" not in locals():
                await engine.dispose()
        except Exception:
            pass
    except Exception as e:
        result["error"] = str(e)
    return result


async def _test_retrieval(tenant: str, query: str, k: int) -> dict[str, Any]:
    """Run dense/sparse/graph/hybrid and reranker stages for one query."""
    out: dict[str, Any] = {"query": query, "tenant": tenant, "k": k}
    t0 = time.monotonic()
    try:
        from backend.graph.container import ServiceContainer

        container = ServiceContainer()
        container.init()
        hr = container.hybrid_retriever
        reranker = container.reranker

        # dense raw
        dense_raw = {}
        dense_distances: list[float] = []
        try:
            if hasattr(hr.vector_store, "query_async"):
                dense_raw = await hr.vector_store.query_async(query, n_results=k * 2, tenant_id=tenant)
            else:
                import asyncio as _aio

                dense_raw = await _aio.to_thread(hr.vector_store.query, query, n_results=k * 2, tenant_id=tenant)
            dists = (dense_raw.get("distances", [[]])[0] or []) if dense_raw else []
            dense_distances = [float(x) for x in dists if x is not None]
            out["dense"] = {
                "documents": dense_raw.get("documents", [[]])[0][:5] if dense_raw.get("documents") else [],
                "distances": dense_distances[:5],
                "count": len(dense_distances),
            }
        except Exception as e:
            out["dense"] = {"error": str(e)}

        # sparse raw
        try:
            if hasattr(hr.bm25, "retrieve_async"):
                try:
                    sparse_raw = await hr.bm25.retrieve_async(query, k=k * 2, tenant_id=tenant)
                except TypeError:
                    sparse_raw = await hr.bm25.retrieve_async(query, k=k * 2)
            else:
                import asyncio as _aio

                def _sync():
                    try:
                        return hr.bm25.retrieve(query, k=k * 2, tenant_id=tenant)
                    except TypeError:
                        return hr.bm25.retrieve(query, k=k * 2)

                sparse_raw = await _aio.to_thread(_sync)
            out["sparse"] = {
                "count": len(sparse_raw),
                "top": [{"content": r.get("content", "")[:120].replace("\n", " "), "score": r.get("score", 0.0)} for r in sparse_raw[:5]],
                "scores": [r.get("score", 0.0) for r in sparse_raw[:5]],
            }
        except Exception as e:
            out["sparse"] = {"error": str(e)}

        # hybrid RRF
        try:
            hybrid = await hr.retrieve(query, k=k, tenant_id=tenant)
            out["hybrid"] = {
                "count": len(hybrid),
                "top": [
                    {
                        "content": r.get("content", "")[:120].replace("\n", " "),
                        "score": round(float(r.get("score", 0.0) or 0.0), 6),
                        "distance": r.get("distance"),
                        "rerank_score": r.get("rerank_score"),
                    }
                    for r in hybrid[:5]
                ],
                "distances": [r.get("distance") for r in hybrid[:5]],
                "scores": [round(float(r.get("score", 0.0) or 0.0), 6) for r in hybrid[:5]],
            }
        except Exception as e:
            out["hybrid"] = {"error": str(e)}

        # reranker stage separately (if not already)
        try:
            # If hybrid already reranked, show reranker output
            # Re-run reranker on hybrid candidates for explicit stage
            if out.get("hybrid") and "error" not in out["hybrid"]:
                # reranker is already applied in nodes; here we show its output via hybrid
                out["reranker"] = {
                    "provider": getattr(settings, "RERANKER_PROVIDER", "none"),
                    "model": getattr(settings, "RERANKER_MODEL", ""),
                    "top_k": len(out["hybrid"]["top"]),
                }
            else:
                out["reranker"] = {"provider": getattr(settings, "RERANKER_PROVIDER", "none"), "note": "no hybrid results to rerank"}
        except Exception as e:
            out["reranker"] = {"error": str(e)}

        out["latency_ms"] = round((time.monotonic() - t0) * 1000, 1)
    except Exception as e:
        out["error"] = str(e)
        out["latency_ms"] = round((time.monotonic() - t0) * 1000, 1)
    return out


async def run_diagnostics(tenant: str, query: str, k: int, explain: bool = False) -> dict[str, Any]:
    """Main diagnostics: config + DB + retrieval stages."""
    # Ensure tracing is initialized for retriever spans
    try:
        from backend.core.observability import setup_otel_tracing, get_tracer

        try:
            get_tracer()
        except RuntimeError:
            setup_otel_tracing(service_name="diagnostics", otlp_endpoint=None, use_console=False)
    except Exception:
        pass
    diag: dict[str, Any] = {}

    # Config
    emb_model = getattr(settings, "EMBEDDING_MODEL", "")
    expected_dim = _resolve_model_dim(emb_model)
    cfg_dim = getattr(settings, "VECTOR_STORE_DIM", 768)
    provider = get_embedding_provider()
    try:
        q_dim = len(provider.embed_query("test probe for dim check"))
        q_dim_error = None
    except Exception as e:
        q_dim = None
        q_dim_error = str(e)

    diag["config"] = {
        "embedding_model": emb_model,
        "expected_dim": expected_dim,
        "vector_store_dim": cfg_dim,
        "embedding_provider": getattr(settings, "EMBEDDING_PROVIDER", "auto"),
        "llm_provider": getattr(settings, "LLM_PROVIDER", ""),
        "vector_store_provider": getattr(settings, "VECTOR_STORE_PROVIDER", ""),
        "sparse_provider": getattr(settings, "SPARSE_PROVIDER", ""),
        "reranker_provider": getattr(settings, "RERANKER_PROVIDER", ""),
        "reranker_model": getattr(settings, "RERANKER_MODEL", ""),
        "graph_provider": getattr(settings, "GRAPH_PROVIDER", ""),
        "tenant": tenant,
        "relevance_threshold": getattr(settings, "RELEVANCE_THRESHOLD", 0.5),
        "grounding_threshold": getattr(settings, "GROUNDING_THRESHOLD", 0.5),
        "vector_distance_threshold": getattr(settings, "VECTOR_DISTANCE_THRESHOLD", 0.65),
        "reranker_threshold": getattr(settings, "RERANKER_THRESHOLD", 0.5),
        "rrf_threshold": getattr(settings, "RRF_THRESHOLD", 0.008),
        "sparse_threshold": getattr(settings, "SPARSE_SCORE_THRESHOLD", 0.01),
        "ef_search": getattr(settings, "PGVECTOR_EF_SEARCH", 40),
        "use_halfvec": bool(getattr(settings, "PGVECTOR_USE_HALFVEC", False)),
        "filtered_tenant": getattr(settings, "PGVECTOR_FILTERED_INDEX_TENANT", None),
        "enable_seqscan_off": bool(getattr(settings, "PGVECTOR_ENABLE_SEQSCAN_OFF", False)),
        "query_vector_dim": q_dim,
        "query_vector_error": q_dim_error,
        "provider_model": getattr(provider, "model", ""),
        "provider_dim": getattr(provider, "dim", None),
    }

    # DB counts
    diag["counts"] = await _get_db_counts(tenant)

    # Retrieval stages for one query
    diag["retrieval"] = await _test_retrieval(tenant, query, k)

    # Additional queries for distance distribution if requested
    if explain:
        queries = [
            query,
            "Do unused annual learning funds roll over?",
            "What is Project Hyperion TTL?",
            "Can a patient take Compound X-49 with Aspirin?",
            "What is the capital of France?",
        ]
        dists_all: dict[str, Any] = {}
        for q in queries:
            r = await _test_retrieval(tenant, q, k)
            dists_all[q[:40]] = {
                "dense_distances": r.get("dense", {}).get("distances", []),
                "hybrid_distances": r.get("hybrid", {}).get("distances", []),
                "hybrid_count": r.get("hybrid", {}).get("count", 0),
            }
        diag["distance_distribution"] = dists_all

    return diag


def _print_human(diag: dict[str, Any]) -> None:
    cfg = diag.get("config", {})
    counts = diag.get("counts", {})
    retr = diag.get("retrieval", {})

    print("\n" + "=" * 72)
    print("🔍 RETRIEVAL DIAGNOSTICS")
    print("=" * 72)
    print(f"Tenant:              {cfg.get('tenant')}  (query tenant)")
    print(f"Embedding model:     {cfg.get('embedding_model')}  provider_dim={cfg.get('provider_dim')} expected_dim={cfg.get('expected_dim')}")
    print(f"VECTOR_STORE_DIM:    {cfg.get('vector_store_dim')}  db_vector_dim={counts.get('db_vector_dim')} type={counts.get('db_vector_type')}")
    print(f"Query vector dim:    {cfg.get('query_vector_dim')}  error={cfg.get('query_vector_error')}")
    print(f"DB vector dim match: {'✓' if cfg.get('query_vector_dim') == counts.get('db_vector_dim') == cfg.get('vector_store_dim') else '✗ MISMATCH'}")
    print(f"Embedding provider:  {cfg.get('embedding_provider')}  vector_store={cfg.get('vector_store_provider')} sparse={cfg.get('sparse_provider')}")
    print(f"Reranker:            {cfg.get('reranker_provider')} / {cfg.get('reranker_model')}")
    print(f"Relevance thresh:    {cfg.get('relevance_threshold')}  Grounding: {cfg.get('grounding_threshold')}  ef_search={cfg.get('ef_search')}")
    print(f"Calibrated thresh:   vector_dist={cfg.get('vector_distance_threshold')}  reranker={cfg.get('reranker_threshold')}  rrf={cfg.get('rrf_threshold')}  sparse={cfg.get('sparse_threshold')}")
    print(f"Scale opts:          halfvec={cfg.get('use_halfvec')}  filtered_tenant={cfg.get('filtered_tenant')}  enable_seqscan_off={cfg.get('enable_seqscan_off')}")
    print("-" * 72)
    print(f"Documents:           {counts.get('documents')}")
    print(f"vector_chunks total: {counts.get('vector_chunks_total')}  tenant {cfg.get('tenant')}: {counts.get('vector_tenant_count')}")
    print(f"  by tenant:         {counts.get('vector_by_tenant')}")
    print(f"sparse_chunks total: {counts.get('sparse_chunks_total')}")
    print(f"  by tenant:         {counts.get('sparse_by_tenant')}")
    print(f"HNSW indexes:        {counts.get('hnsw_indexes')}")
    print(f"GIN indexes:         {counts.get('gin_indexes')}")
    if counts.get("error"):
        print(f"DB error:            {counts['error']}")
    print("-" * 72)
    print(f"Test query:          {retr.get('query')!r}  k={retr.get('k')}  tenant={retr.get('tenant')}  latency={retr.get('latency_ms')}ms")
    if "error" in retr:
        print(f"  error: {retr['error']}")
    if "dense" in retr:
        d = retr["dense"]
        if "error" in d:
            print(f"  dense error: {d['error']}")
        else:
            print(f"  dense:  count={d.get('count')}  distances(top5)={d.get('distances')}")
            for i, doc in enumerate(d.get("documents", [])[:3]):
                print(f"    [{i}] {doc[:100].replace(chr(10),' ')}")
    if "sparse" in retr:
        s = retr["sparse"]
        if "error" in s:
            print(f"  sparse error: {s['error']}")
        else:
            print(f"  sparse: count={s.get('count')}  scores={s.get('scores')}")
            for i, t in enumerate(s.get("top", [])[:3]):
                print(f"    [{i}] score={t['score']:.4f} {t['content'][:100]}")
    if "hybrid" in retr:
        h = retr["hybrid"]
        if "error" in h:
            print(f"  hybrid error: {h['error']}")
        else:
            print(f"  hybrid RRF+dedup+rerank: count={h.get('count')}  scores={h.get('scores')}  distances={h.get('distances')}")
            for i, t in enumerate(h.get("top", [])[:5]):
                print(f"    [{i}] score={t['score']} dist={t['distance']} {t['content'][:100]}")
    if "reranker" in retr:
        print(f"  reranker: {retr['reranker']}")
    if "distance_distribution" in diag:
        print("-" * 72)
        print("Distance distribution (multiple queries):")
        for q, d in diag["distance_distribution"].items():
            print(f"  {q!r}: hybrid_count={d['hybrid_count']} dense={d['dense_distances'][:3]} hybrid_dist={d['hybrid_distances'][:3]}")
    print("=" * 72)


async def _cli_async(args: argparse.Namespace) -> int:
    if args.retrieval:
        diag = await run_diagnostics(tenant=args.tenant, query=args.query, k=args.k, explain=args.explain)
        if args.json:
            import json

            print(json.dumps(diag, indent=2, default=str))
        else:
            _print_human(diag)
        # Quick verdict
        cfg = diag.get("config", {})
        counts = diag.get("counts", {})
        if cfg.get("query_vector_dim") and counts.get("db_vector_dim") and cfg["query_vector_dim"] != counts["db_vector_dim"]:
            print("\n⚠️  DIM MISMATCH — query vs DB vs config differ. Re-ingest with correct VECTOR_STORE_DIM or run alembic.")
            return 2
        if counts.get("vector_tenant_count") == 0 and counts.get("vector_chunks_total", 0) > 0:
            print(f"\n⚠️  TENANT MISMATCH — {counts['vector_chunks_total']} vectors exist but 0 for tenant {args.tenant!r}. Check ingestion tenant.")
            return 2
        if diag.get("retrieval", {}).get("hybrid", {}).get("count", 0) == 0 and counts.get("vector_tenant_count", 0) > 5:
            print("\n⚠️  RETRIEVAL 0 — vectors exist but hybrid returned 0. Check distance threshold / sparse fallback / reranker.")
            return 2
        return 0
    else:
        # No mode selected — default to retrieval
        diag = await run_diagnostics(tenant=args.tenant, query=args.query, k=args.k, explain=False)
        _print_human(diag)
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Retrieval diagnostics for Self-Healing RAG")
    parser.add_argument("--retrieval", action="store_true", help="Run retrieval stage diagnostics")
    parser.add_argument("--tenant", type=str, default="default", help="Tenant to query (default: default)")
    parser.add_argument("--query", type=str, default="What is the one-time home office equipment stipend for new hires at Acme Corp?", help="Test query")
    parser.add_argument("--k", type=int, default=5, help="Top-k for retrieval")
    parser.add_argument("--explain", action="store_true", help="Include distance distribution for multiple queries and EXPLAIN ANALYZE")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of human table")
    args = parser.parse_args()
    return asyncio.run(_cli_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
