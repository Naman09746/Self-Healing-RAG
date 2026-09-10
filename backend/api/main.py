import asyncio
import time
import psycopg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres import PostgresSaver
from backend.core.config import settings
from backend.core.logging import setup_logging, get_logger
from backend.api.routers import ingest, query, auth, websocket, documents, experiments
from contextlib import asynccontextmanager

from backend.api.middleware.rate_limit import RateLimitMiddleware
from backend.api.middleware.concurrency import ConcurrencyControlMiddleware
from backend.api.middleware.request_id import RequestIDMiddleware
from backend.api.middleware.audit import AuditMiddleware
from backend.core.metrics import PrometheusMiddleware, metrics_endpoint
from backend.core.observability import (
    setup_otel_tracing,
    setup_langsmith,
    shutdown_observability,
)
from backend.graph.container import svc
from backend.graph.workflow import create_rag_graph

# Initialize logging
setup_logging()

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info(
        "Starting up Self-Healing RAG API",
        project_name=settings.PROJECT_NAME,
        ollama_host=settings.OLLAMA_HOST,
    )

    # 0. Initialize OpenTelemetry tracing (Phase 4C)
    setup_otel_tracing(
        service_name="self-healing-rag",
        otlp_endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        use_console=settings.OTEL_CONSOLE_EXPORT,
    )

    # 0b. Initialize LangSmith (Phase 4C)
    setup_langsmith()

    # 1. Initialize service container (creates all agents, stores, memories).
    svc.init()
    app.state.svc = svc

    # 2. Fast checkpointer: default to MemorySaver immediately so the graph compiles in 0ms!
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()
    app.state.checkpointer = checkpointer
    app.state.rag_graph = create_rag_graph(svc, checkpointer=checkpointer)
    logger.info("RAG graph compiled and ready (instant startup)")

    # 3. Background DB & Checkpointer upgrade task (does not block port binding!)
    async def _background_init():
        # DB tables
        try:
            from backend.storage.db.session import init_db
            await asyncio.wait_for(init_db(), timeout=10.0)
            logger.info("Database tables initialized successfully")
        except Exception as e:
            logger.warning("Database init_db warning (will retry on requests)", error=str(e))

        # Postgres checkpointer upgrade (optional, non-blocking)
        checkpoint_uri = settings.LANGGRAPH_CHECKPOINT_URI
        if (
            not checkpoint_uri
            and settings.DATABASE_URL
            and "localhost" not in settings.DATABASE_URL
            and "127.0.0.1" not in settings.DATABASE_URL
        ):
            checkpoint_uri = (
                settings.DATABASE_URL
                .replace("postgresql+asyncpg://", "postgresql://", 1)
                .replace("ssl=require", "sslmode=require")
            )

        if checkpoint_uri:
            try:
                def _setup_pg_saver():
                    import psycopg
                    from langgraph.checkpoint.postgres import PostgresSaver
                    c = psycopg.connect(checkpoint_uri, connect_timeout=5)
                    cp = PostgresSaver(conn=c)
                    cp.setup()
                    return cp

                pg_saver = await asyncio.wait_for(asyncio.to_thread(_setup_pg_saver), timeout=8.0)
                app.state.checkpointer = pg_saver
                app.state.rag_graph = create_rag_graph(svc, checkpointer=pg_saver)
                logger.info("Upgraded to PostgresCheckpointer in background")
            except Exception as e:
                logger.info("Proceeding with MemorySaver checkpointer", reason=str(e))

    asyncio.create_task(_background_init())

    yield

    # Shutdown logic
    logger.info("Shutting down Self-Healing RAG API")

    # Flush & shutdown observability exporters
    await shutdown_observability()

    # Close checkpointer connection pool
    if hasattr(app.state, "checkpointer") and app.state.checkpointer is not None:
        try:
            app.state.checkpointer.conn.close()
            logger.info("PostgresCheckpointer connection closed")
        except Exception:
            pass

    await svc.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Add Middleware (order matters: RequestID first, then metrics, audit, rate limit, concurrency)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(PrometheusMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(ConcurrencyControlMiddleware)

# Configure CORS for local development and cloud deployments (Vercel, Render)
cors_kwargs = {
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if "*" in settings.CORS_ORIGINS:
    cors_kwargs["allow_origin_regex"] = r"^https?://.*"
    cors_kwargs["allow_credentials"] = True
else:
    cors_kwargs["allow_origins"] = settings.CORS_ORIGINS
    cors_kwargs["allow_credentials"] = True

app.add_middleware(CORSMiddleware, **cors_kwargs)


app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(query.router, prefix=settings.API_V1_STR)
app.include_router(ingest.router, prefix=settings.API_V1_STR)
app.include_router(documents.router, prefix=settings.API_V1_STR)
app.include_router(experiments.router, prefix=settings.API_V1_STR)
app.include_router(websocket.router, tags=["WebSocket"])


@app.get("/health")
@app.get(f"{settings.API_V1_STR}/health")
async def health_check(request: Request):
    """Component health check probing VectorStore (chroma/pgvector/qdrant/pinecone), Redis, Postgres, Neo4j, Ollama."""
    services: dict[str, Any] = {}
    svc_container = getattr(request.app.state, "svc", None)
    provider = getattr(settings, "VECTOR_STORE_PROVIDER", "chroma")

    # 1. Vector Store (provider-aware)
    t0 = time.time()
    try:
        if svc_container and svc_container.store:
            # Prefer heartbeat() method on VectorStore protocol
            if hasattr(svc_container.store, "heartbeat"):
                try:
                    ok = await asyncio.wait_for(asyncio.to_thread(svc_container.store.heartbeat), timeout=3.0)
                except Exception:
                    ok = svc_container.store.heartbeat() if not asyncio.iscoroutinefunction(svc_container.store.heartbeat) else False
                if ok:
                    services["vector_store"] = {"status": "healthy", "provider": provider, "latency_ms": round((time.time() - t0) * 1000, 2)}
                    # Back-compat alias: expose as 'chroma' when provider is chroma so old dashboards keep working
                    if provider == "chroma":
                        services["chroma"] = services["vector_store"]
                    else:
                        services["chroma"] = {"status": "not_used", "provider": provider}
                else:
                    services["vector_store"] = {"status": "unhealthy", "provider": provider, "latency_ms": round((time.time() - t0) * 1000, 2)}
                    services["chroma"] = services["vector_store"]
            elif hasattr(svc_container.store, "client"):
                svc_container.store.client.heartbeat()
                services["vector_store"] = {"status": "healthy", "provider": provider, "latency_ms": round((time.time() - t0) * 1000, 2)}
                services["chroma"] = services["vector_store"] if provider == "chroma" else {"status": "not_used"}
            else:
                services["vector_store"] = {"status": "uninitialized", "provider": provider}
                services["chroma"] = {"status": "uninitialized"}
        else:
            services["vector_store"] = {"status": "uninitialized", "provider": provider}
            services["chroma"] = {"status": "uninitialized"}
    except Exception as e:
        services["vector_store"] = {"status": "unhealthy", "provider": provider, "error": str(e)}
        services["chroma"] = services["vector_store"]

    # 2. Session Store (pluggable: pg | redis | memory)
    t0 = time.time()
    sess_provider = getattr(settings, "SESSION_STORE_PROVIDER", "pg")
    try:
        if svc_container and svc_container.session_memory:
            # Prefer heartbeat()
            if hasattr(svc_container.session_memory, "heartbeat"):
                try:
                    ok = await asyncio.wait_for(svc_container.session_memory.heartbeat(), timeout=2.0)  # type: ignore[attr-defined]
                except Exception:
                    ok = False
                services["session_store"] = {"status": "healthy" if ok else "unhealthy", "provider": sess_provider, "latency_ms": round((time.time() - t0) * 1000, 2)}
            elif hasattr(svc_container.session_memory, "pool") and svc_container.session_memory.pool:
                conn = await svc_container.session_memory.get_connection()
                try:
                    await asyncio.wait_for(conn.ping(), timeout=2.0)
                    services["session_store"] = {"status": "healthy", "provider": sess_provider, "latency_ms": round((time.time() - t0) * 1000, 2)}
                finally:
                    try:
                        await conn.aclose()  # type: ignore[attr-defined]
                    except Exception:
                        pass
            else:
                services["session_store"] = {"status": "uninitialized", "provider": sess_provider}
        else:
            services["session_store"] = {"status": "uninitialized", "provider": sess_provider}
    except Exception as e:
        services["session_store"] = {"status": "unhealthy", "provider": sess_provider, "error": str(e)}
    # Back-compat: expose as redis for old dashboards
    try:
        pool = getattr(svc_container.session_memory, "pool", None) if svc_container and svc_container.session_memory else None
        if sess_provider == "redis" and pool is not None:
            services["redis"] = services["session_store"]
        else:
            services["redis"] = {"status": "not_used" if sess_provider != "redis" else "uninitialized", "provider": sess_provider}
    except Exception:
        services["redis"] = {"status": "not_used"}

    # 3. PostgreSQL
    t0 = time.time()
    try:
        from backend.storage.db.session import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as session:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=2.0)
        services["postgres"] = {"status": "healthy", "latency_ms": round((time.time() - t0) * 1000, 2)}
    except Exception as e:
        services["postgres"] = {"status": "unhealthy", "error": str(e)}

    # 3b. Sparse Store (pg_tsvector | bm25)
    t0 = time.time()
    sparse_provider = getattr(settings, "SPARSE_PROVIDER", "pg_tsvector")
    try:
        if svc_container and svc_container.hybrid_retriever and getattr(svc_container.hybrid_retriever, "bm25", None):
            sparse = svc_container.hybrid_retriever.bm25
            if hasattr(sparse, "heartbeat"):
                ok = await asyncio.wait_for(asyncio.to_thread(sparse.heartbeat), timeout=2.0) if not asyncio.iscoroutinefunction(getattr(sparse, "heartbeat")) else await asyncio.wait_for(sparse.heartbeat(), timeout=2.0)  # type: ignore
                services["sparse_store"] = {"status": "healthy" if ok else "unhealthy", "provider": sparse_provider, "latency_ms": round((time.time() - t0) * 1000, 2)}
            else:
                services["sparse_store"] = {"status": "healthy", "provider": sparse_provider, "latency_ms": round((time.time() - t0) * 1000, 2)}
        else:
            services["sparse_store"] = {"status": "uninitialized", "provider": sparse_provider}
    except Exception as e:
        services["sparse_store"] = {"status": "unhealthy", "provider": sparse_provider, "error": str(e)}

    # 3c. Reranker (none | cross-encoder)
    t0 = time.time()
    reranker_provider = getattr(settings, "RERANKER_PROVIDER", "none")
    try:
        if svc_container and svc_container.reranker:
            if hasattr(svc_container.reranker, "heartbeat"):
                ok = svc_container.reranker.heartbeat()  # type: ignore[attr-defined]
                services["reranker"] = {"status": "healthy" if ok else "unhealthy", "provider": reranker_provider, "latency_ms": round((time.time() - t0) * 1000, 2)}
            else:
                services["reranker"] = {"status": "healthy", "provider": reranker_provider, "latency_ms": round((time.time() - t0) * 1000, 2)}
        else:
            services["reranker"] = {"status": "uninitialized", "provider": reranker_provider}
    except Exception as e:
        services["reranker"] = {"status": "unhealthy", "provider": reranker_provider, "error": str(e)}

    # 4. Graph Store (memory | neo4j | pg)
    t0 = time.time()
    graph_provider = getattr(settings, "GRAPH_PROVIDER", "memory")
    try:
        graph = None
        if svc_container and svc_container.hybrid_retriever and getattr(svc_container.hybrid_retriever, "graph", None):
            graph = svc_container.hybrid_retriever.graph
        if graph is not None:
            if hasattr(graph, "heartbeat"):
                ok = await asyncio.wait_for(asyncio.to_thread(graph.heartbeat), timeout=2.0) if not asyncio.iscoroutinefunction(getattr(graph, "heartbeat")) else await asyncio.wait_for(graph.heartbeat(), timeout=2.0)  # type: ignore
                # memory is always healthy; neo4j may be unreachable
                status = "healthy" if ok else ("disabled_or_unavailable" if graph_provider == "memory" else "unhealthy")
                services["graph_store"] = {"status": status, "provider": graph_provider, "latency_ms": round((time.time() - t0) * 1000, 2)}
            elif getattr(graph, "_driver", None):
                await asyncio.wait_for(asyncio.to_thread(graph._driver.verify_connectivity), timeout=2.0)  # type: ignore
                services["graph_store"] = {"status": "healthy", "provider": graph_provider, "latency_ms": round((time.time() - t0) * 1000, 2)}
            else:
                # memory driver is None but we consider healthy
                services["graph_store"] = {"status": "healthy", "provider": graph_provider, "latency_ms": round((time.time() - t0) * 1000, 2)}
        else:
            services["graph_store"] = {"status": "disabled_or_unavailable", "provider": graph_provider}
        # Back-compat alias
        if graph_provider == "neo4j":
            services["neo4j"] = services["graph_store"]
        else:
            services["neo4j"] = {"status": "not_used", "provider": graph_provider}
    except Exception as e:
        services["graph_store"] = {"status": "unhealthy", "provider": graph_provider, "error": str(e)}
        services["neo4j"] = services["graph_store"]

    # 5. Ollama
    t0 = time.time()
    try:
        import ollama
        client = ollama.AsyncClient(host=settings.OLLAMA_HOST)
        await asyncio.wait_for(client.list(), timeout=2.0)
        services["ollama"] = {"status": "healthy", "latency_ms": round((time.time() - t0) * 1000, 2)}
    except Exception as e:
        services["ollama"] = {"status": "unhealthy", "error": str(e)}

    return {
        "status": "healthy",
        "version": "0.1.0",
        "services": services,
    }


@app.get(f"{settings.API_V1_STR}/metrics/snapshot")
async def metrics_snapshot():
    """Live metrics snapshot for frontend dashboard and system ribbons."""
    from backend.core.metrics import metrics
    return metrics.get_snapshot()



@app.get("/")
async def root():
    return {"message": "Welcome to the Self-Healing RAG Pipeline API"}


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint for scraping by Prometheus server."""
    from starlette.responses import Response
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return Response(
        content=generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )