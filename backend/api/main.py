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
    """Component health check probing Chroma, Redis, Postgres, Neo4j, and Ollama."""
    services: dict[str, Any] = {}
    svc_container = getattr(request.app.state, "svc", None)

    # 1. ChromaDB
    t0 = time.time()
    try:
        if svc_container and svc_container.store and hasattr(svc_container.store, "client"):
            svc_container.store.client.heartbeat()
            services["chroma"] = {"status": "healthy", "latency_ms": round((time.time() - t0) * 1000, 2)}
        else:
            services["chroma"] = {"status": "uninitialized"}
    except Exception as e:
        services["chroma"] = {"status": "unhealthy", "error": str(e)}

    # 2. Redis
    t0 = time.time()
    try:
        if svc_container and svc_container.session_memory and svc_container.session_memory.pool:
            conn = await svc_container.session_memory.get_connection()
            try:
                await asyncio.wait_for(conn.ping(), timeout=2.0)
                services["redis"] = {"status": "healthy", "latency_ms": round((time.time() - t0) * 1000, 2)}
            finally:
                await conn.aclose()
        else:
            services["redis"] = {"status": "uninitialized"}
    except Exception as e:
        services["redis"] = {"status": "unhealthy", "error": str(e)}

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

    # 4. Neo4j
    t0 = time.time()
    try:
        if (
            svc_container
            and svc_container.hybrid_retriever
            and svc_container.hybrid_retriever.graph
            and getattr(svc_container.hybrid_retriever.graph, "_driver", None)
        ):
            await asyncio.wait_for(
                asyncio.to_thread(svc_container.hybrid_retriever.graph._driver.verify_connectivity),
                timeout=2.0,
            )
            services["neo4j"] = {"status": "healthy", "latency_ms": round((time.time() - t0) * 1000, 2)}
        else:
            services["neo4j"] = {"status": "disabled_or_unavailable"}
    except Exception as e:
        services["neo4j"] = {"status": "unhealthy", "error": str(e)}

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