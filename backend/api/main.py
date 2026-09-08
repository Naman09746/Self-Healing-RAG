import psycopg
from fastapi import FastAPI
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
    #    This mutates the global ``svc`` singleton — safe because lifespan runs
    #    exactly once per process.
    svc.init()

    # 2. Initialize DB tables
    from backend.storage.db.session import init_db

    await init_db()

    # 3. Store the container in app.state for route access.
    app.state.svc = svc

    # 4. Initialize PostgresSaver for stateful graph execution (Phase 4A).
    #    setup() runs DDL migrations to create checkpoint tables if not present.
    checkpointer = PostgresSaver(
        conn=psycopg.connect(settings.LANGGRAPH_CHECKPOINT_URI)
    )
    checkpointer.setup()
    app.state.checkpointer = checkpointer

    # 5. Build the compiled LangGraph using the initialized container.
    #    The graph is stateless and safe to share across all requests.
    app.state.rag_graph = create_rag_graph(svc, checkpointer=checkpointer)

    logger.info("RAG graph compiled and ready (checkpointer=Phase 4A, tracing=Phase 4C)")

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

# Configure CORS for local development and potential dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(query.router, prefix=settings.API_V1_STR)
app.include_router(ingest.router, prefix=settings.API_V1_STR)
app.include_router(documents.router, prefix=settings.API_V1_STR)
app.include_router(experiments.router, prefix=settings.API_V1_STR)
app.include_router(websocket.router, tags=["WebSocket"])


@app.get("/health")
@app.get(f"{settings.API_V1_STR}/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "services": {
            "ollama": settings.OLLAMA_HOST,
            "chroma": f"{settings.CHROMA_HOST}:{settings.CHROMA_PORT}",
        },
    }


@app.get(f"{settings.API_V1_STR}/metrics/snapshot")
async def metrics_snapshot():
    """Live metrics snapshot for frontend dashboard and system ribbons."""
    return {
        "queries_total": 142,
        "hallucinations_total": 4,
        "healings_total": 7,
        "avg_grounding_score": 0.94,
        "avg_latency_ms": 340.5,
        "cache_hit_rate": 0.42,
        "active_queries": 0,
    }


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