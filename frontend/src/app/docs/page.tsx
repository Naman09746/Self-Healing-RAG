"use client";

import { useEffect, useState, useRef } from "react";
import {
  Menu,
  X,
  ArrowRight,
  BookOpen,
  Search,
  ChevronRight,
  ExternalLink,
  GitBranch,
  Code2,
  Layers,
  Shield,
  Cpu,
  Zap,
  Database,
  FileText,
  Network,
  Bot,
  Workflow,
  Eye,
  Lock,
  Globe,
  ArrowUp,
  Menu as MenuIcon,
  Loader2,
} from "lucide-react";

/* ─── Sidebar Nav Items ──────────────────────────────── */
const NAV_SECTIONS = [
  {
    title: "Getting Started",
    items: [
      { id: "introduction", label: "Introduction", icon: BookOpen },
      { id: "quickstart", label: "Quickstart Guide", icon: Zap },
      { id: "architecture", label: "Architecture Overview", icon: Layers },
    ],
  },
  {
    title: "Core Concepts",
    items: [
      { id: "agents", label: "Multi-Agent Pipeline", icon: Bot },
      { id: "retrieval", label: "Hybrid Retrieval", icon: Database },
      { id: "healing", label: "Self-Healing", icon: Cpu },
      { id: "hallucination", label: "Hallucination Detection", icon: Shield },
    ],
  },
  {
    title: "Deployment",
    items: [
      { id: "docker", label: "Docker Deployment", icon: Globe },
      { id: "kubernetes", label: "Kubernetes", icon: Network },
      { id: "configuration", label: "Configuration", icon: Code2 },
      { id: "security", label: "Security", icon: Lock },
    ],
  },
  {
    title: "API Reference",
    items: [
      { id: "api-overview", label: "API Overview", icon: Code2 },
      { id: "api-query", label: "Query Endpoint", icon: Workflow },
      { id: "api-ingest", label: "Ingest Endpoint", icon: FileText },
      { id: "api-evaluate", label: "Evaluate Endpoint", icon: Eye },
    ],
  },
];

/* ─── Section Content ────────────────────────────────── */
const SECTION_CONTENT: Record<string, { title: string; content: string; code?: string }> = {
  introduction: {
    title: "Introduction",
    content: `Nexus Core is an enterprise-grade, self-healing multi-agent RAG (Retrieval-Augmented Generation) platform designed to deliver verified, factual answers from your knowledge base with automatic hallucination detection and correction.

The system uses a pipeline of seven specialized agents — Intake, Planner, Retriever, Generator, Critic, Healer, and Output — orchestrated via LangGraph to process queries, retrieve context, generate answers, verify claims, and automatically correct unverifiable outputs.

Key capabilities:
• Hybrid retrieval across vector, keyword, and graph stores
• Real-time hallucination detection with claim-level verification
• Automatic self-healing when unverifiable claims are detected
• Enterprise-grade security with RBAC, audit logging, and encryption
• Full observability with telemetry and metrics collection`,
  },
  quickstart: {
    title: "Quickstart Guide",
    content: `Getting started with Nexus Core is straightforward.

Using the Dashboard:

1. Open the Dashboard — Click "Launch App" on the homepage or navigate to /dashboard
2. Ask a Question — Type any question about your documents in the chat panel
3. View Results — Every answer includes confidence scores, source citations, and verification status
4. Upload Documents — Use the Documents panel to upload PDF, DOCX, or TXT files
5. Monitor Pipeline — Watch the live pipeline visualization as your query processes through each agent

Key Features:
• Multi-agent pipeline automatically retrieves, generates, and verifies every answer
• Hallucination detection catches unverifiable claims in real-time
• Self-healing retries with adjusted parameters when low-confidence results are detected
• All responses include grounding scores and source provenance

The system works out of the box — no setup required. Just navigate to your instance and start querying.`,
  },
  architecture: {
    title: "Architecture Overview",
    content: `Nexus Core follows a modular microservices architecture with six core components:

1. API Gateway — FastAPI-based entry point with rate limiting, authentication, and request routing
2. Agent Pipeline — LangGraph-orchestrated multi-agent workflow
3. Storage Layer — Hybrid storage with ChromaDB (vectors), Neo4j (knowledge graph), BM25 (keyword index), and PostgreSQL (metadata)
4. Ingestion Pipeline — Document processing with chunking, embedding, and indexing
5. Memory System — Session management with query caching and conversation history
6. Observability — Prometheus metrics, structured logging, and audit trails

Data Flow:
User Query → API Gateway → Intake Agent → Planner Agent → Retriever Agent → Generator Agent → Critic Agent → Healer Agent (if needed) → Output Agent → Response`,
  },
  agents: {
    title: "Multi-Agent Pipeline",
    content: `The core of Nexus Core is a LangGraph-based multi-agent pipeline with specialized agents:

Intake Agent — Validates and normalizes incoming queries, checks for injection attempts via the Prompt Injection Guard, and enriches with session context.

Planner Agent — Decomposes complex queries into sub-queries, identifies required knowledge domains, and generates an optimized retrieval plan.

Retriever Agent — Executes hybrid search across all storage backends using Reciprocal Rank Fusion (RRF) for result merging, with BM25 for keyword precision and dense vectors for semantic understanding.

Generator Agent — Constructs contextual answers using retrieved chunks respecting context window limits, with source citations embedded in the response.

Critic Agent — Extracts every factual claim from generated text and verifies each against retrieved context, classifying claims as verified, unsupported, or contradicted.

Healer Agent — Activates when unverifiable claims are detected, rewriting the query and re-retrieving context with adjusted parameters through up to N retry attempts.

Output Agent — Formats the final response with confidence scores, source provenance, and optional feedback tracking.`,
  },
  retrieval: {
    title: "Hybrid Retrieval",
    content: `Nexus Core combines three retrieval strategies for maximum relevance:

Vector Search (ChromaDB) — Semantic search using sentence-transformer embeddings with cosine similarity, supporting metadata filtering and MMR diversification for broad coverage.

Keyword Search (BM25) — Token-based exact matching with term frequency-inverse document frequency scoring, ideal for precise terminology and named entities.

Graph Traversal (Neo4j) — Entity-relationship exploration across the knowledge graph, enabling multi-hop reasoning and relationship discovery.

Results are fused using Reciprocal Rank Fusion (RRF), optionally re-ranked through Cross-Encoder for maximum precision. The system supports configurable weights per retrieval strategy.`,
  },
  healing: {
    title: "Self-Healing Mechanism",
    content: `The self-healing loop is triggered when the Critic Agent finds unverifiable or contradicted claims:

1. Detection — Critic identifies claims that cannot be verified against retrieved context
2. Analysis — Healer Agent analyzes what went wrong (ambiguous query, insufficient context, retrieval failure)
3. Rewrite — Healer reformulates the original query with additional context
4. Re-retrieve — Retrieval Agent re-executes with the rewritten query, often with relaxed similarity thresholds
5. Re-generate — Generator produces a new answer from the improved context
6. Re-verify — Critic re-verifies all claims; if still failing, the cycle repeats

The system configures a maximum retry limit (default: 3) to prevent infinite loops. Each retry logs telemetry for observability.`,
  },
  hallucination: {
    title: "Hallucination Detection",
    content: `The Critic Agent implements a multi-step verification process:

1. Claim Extraction — Decomposes the generated answer into atomic factual claims using NLP parsing
2. Grounding Verification — Each claim is checked against retrieved context chunks for evidentiary support
3. Classification — Claims are classified as:
   • Verified — Directly supported by context
   • Unsupported — Neither confirmed nor denied
   • Contradicted — Directly contradicted by context

4. Confidence Scoring — Aggregate score calculated as the proportion of verified claims, weighted by semantic similarity
5. Report — Detailed breakdown of each claim's verification status is included in the response

This approach eliminates AI hallucinations by grounding every output in retrievable evidence.`,
  },
  docker: {
    title: "Docker Deployment",
    content: `Production-ready Docker Compose configuration with all services:

• api — FastAPI application server (port 8000)
• frontend — Next.js application (port 3000)
• chromadb — Vector store (port 8001)
• neo4j — Knowledge graph database (port 7687)
• postgres — Metadata and session store (port 5432)
• redis — Caching and rate limiting (port 6379)

Environment variables are managed via .env file. The system supports health checks, volume persistence, and network isolation between services.`,
  },
  kubernetes: {
    title: "Kubernetes Deployment",
    content: `For production-scale deployments, Nexus Core provides Kubernetes manifests:

Resources:
• Deployments for each microservice with resource limits
• StatefulSets for stateful services (ChromaDB, Neo4j, PostgreSQL)
• Horizontal Pod Autoscalers based on CPU/memory utilization
• Network policies for inter-service communication
• PersistentVolumeClaims for data durability
• Ingress configuration with TLS termination
• ConfigMaps and Secrets for configuration management

Requirements: Kubernetes 1.24+, cert-manager for TLS, and a StorageClass with ReadWriteOnce capability.`,
  },
  configuration: {
    title: "Configuration",
    content: `Nexus Core is configured through environment variables:

Required:
• OPENAI_API_KEY — LLM provider API key
• DATABASE_URL — PostgreSQL connection string
• CHROMA_PERSIST_DIR — Vector store persistence path

Optional:
• NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD — Graph DB credentials
• REDIS_URL — Caching backend
• MAX_RETRIES — Self-healing retry limit (default: 3)
• CONFIDENCE_THRESHOLD — Minimum verification threshold (default: 0.7)
• LOG_LEVEL — Logging verbosity (default: INFO)`,
  },
  security: {
    title: "Security",
    content: `Enterprise-grade security model:

• Authentication — JWT-based with API key rotation and OAuth 2.0 support
• Authorization — Role-Based Access Control (RBAC) with fine-grained permissions
• Encryption — TLS 1.3 for transport, AES-256 for data at rest
• Audit Logging — All queries and system events are logged with tamper-evident trails
• Rate Limiting — Per-tenant and per-user rate limits with configurable windows
• Prompt Injection — Dedicated guard against prompt injection attacks in the Intake Agent
• Data Isolation — Multi-tenant isolation with tenant-scoped vector spaces and database schemas`,
  },
  /* ─── API Reference ─────────────────────────────────── */
  "api-overview": {
    title: "API Overview",
    content: `The Nexus Core API is built with FastAPI and follows RESTful conventions. All endpoints are prefixed with /api/v1.

Authentication is via Bearer token in the Authorization header. Rate limits apply per tenant.

The API provides:
• POST /api/v1/query — Submit a query to the RAG pipeline
• POST /api/v1/ingest — Upload documents for indexing
• GET /api/v1/documents — List indexed documents
• DELETE /api/v1/documents/{id} — Remove a document
• POST /api/v1/evaluate — Run evaluation benchmarks
• GET /api/v1/health — System health check

Interactive API documentation is available at /docs when the server is running.`,
    code: `# Base URL
https://api.nexus-core.com/api/v1

# Headers
Authorization: Bearer <your-api-key>
Content-Type: application/json`,
  },
  "api-query": {
    title: "Query Endpoint",
    content: `Submit a natural language query to the multi-agent RAG pipeline. The system retrieves context, generates an answer, verifies claims, and optionally self-heals.

Request Body:
• query (string, required) — Your question
• top_k (integer, optional, default: 5) — Number of context chunks to retrieve
• stream (boolean, optional, default: false) — Enable streaming response
• session_id (string, optional) — For multi-turn conversations

Response includes the answer text, confidence score, source citations with relevance scores, and per-claim verification details.`,
    code: `curl -X POST https://api.nexus-core.com/api/v1/query \\
  -H "Authorization: Bearer <your-api-key>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "What are the security features?",
    "top_k": 5,
    "session_id": "sess_abc123"
  }'

# Response
{
  "answer": "Nexus Core implements...",
  "confidence": 0.94,
  "sources": [
    {
      "title": "Security Architecture",
      "score": 0.96
    }
  ],
  "claims": [
    {
      "claim": "RBAC is supported",
      "status": "verified"
    }
  ],
  "healed": false,
  "latency_ms": 1200
}`,
  },
  "api-ingest": {
    title: "Ingest Endpoint",
    content: `Upload documents for processing and indexing. Supports PDF, DOCX, TXT, and Markdown formats.

The ingestion pipeline automatically chunks the document, generates embeddings, and indexes across all storage backends (ChromaDB, Neo4j, BM25).

Request: multipart/form-data with a file field
Response includes the document ID, chunk count, and indexing status.

The system also supports async ingestion via the X-Async header for large documents.`,
    code: `curl -X POST https://api.nexus-core.com/api/v1/ingest \\
  -H "Authorization: Bearer <your-api-key>" \\
  -F "file=@report.pdf"

# Response
{
  "document_id": "doc_xyz789",
  "filename": "report.pdf",
  "chunks": 156,
  "status": "indexed",
  "latency_ms": 3400
}`,
  },
  "api-evaluate": {
    title: "Evaluate Endpoint",
    content: `Run evaluation benchmarks against your indexed documents to measure system performance.

The evaluation pipeline runs a set of test queries and measures:
• Answer relevance (cosine similarity to expected answers)
• Grounding accuracy (proportion of verified claims)
• Latency (end-to-end response time)
• Self-heal rate (how often the Critic triggers healing)

Results are stored for trend analysis and can be exported as JSONL for external analysis.`,
    code: `curl -X POST https://api.nexus-core.com/api/v1/evaluate \\
  -H "Authorization: Bearer <your-api-key>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "dataset_id": "eval_weekly_001"
  }'

# Response
{
  "results": {
    "avg_relevance": 0.92,
    "avg_grounding": 0.97,
    "avg_latency_ms": 1450,
    "heal_rate": 0.12,
    "total_queries": 50
  },
  "status": "completed"
}`,
  },
};

/* ─── Sidebar ─────────────────────────────────────────── */
function DocsSidebar({
  activeSection,
  onSectionChange,
  mobileOpen,
  onMobileClose,
}: {
  activeSection: string;
  onSectionChange: (id: string) => void;
  mobileOpen: boolean;
  onMobileClose: () => void;
}) {
  return (
    <>
      {/* Desktop */}
      <aside
        className="hidden md:block w-[260px] shrink-0 h-screen sticky top-0 overflow-y-auto"
        style={{
          borderRight: "1px solid rgba(255,255,255,0.04)",
          background: "rgba(10,10,15,0.95)",
        }}
      >
        <div className="p-4" style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
          <a href="/" className="flex items-center gap-2.5 group">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center transition-all group-hover:shadow-lg"
              style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}
            >
              <BookOpen size={13} className="text-white" />
            </div>
            <span className="text-xs font-semibold" style={{ color: "#e8e8ed" }}>Documentation</span>
          </a>
        </div>
        <nav className="p-3 space-y-4">
          {NAV_SECTIONS.map((section) => (
            <div key={section.title}>
              <p className="text-[9px] font-semibold uppercase tracking-widest px-2 mb-1.5" style={{ color: "#525266" }}>
                {section.title}
              </p>
              <div className="space-y-0.5">
                {section.items.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => {
                      onSectionChange(item.id);
                      onMobileClose();
                    }}
                    className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-[11px] transition-all text-left ${
                      activeSection === item.id
                        ? "bg-indigo-500/10 text-indigo-300"
                        : "text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.03]"
                    }`}
                  >
                    <item.icon size={13} className="shrink-0" />
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </nav>
      </aside>

      {/* Mobile */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-50 md:hidden"
          style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
        >
          <aside
            className="w-[280px] h-full overflow-y-auto"
            style={{
              background: "rgba(10,10,15,0.98)",
              borderRight: "1px solid rgba(255,255,255,0.04)",
            }}
          >
            <div className="flex items-center justify-between p-4" style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}>
                  <BookOpen size={13} className="text-white" />
                </div>
                <span className="text-xs font-semibold" style={{ color: "#e8e8ed" }}>Documentation</span>
              </div>
              <button onClick={onMobileClose} className="p-1 rounded-lg hover:bg-white/5" style={{ color: "#525266" }}>
                <X size={16} />
              </button>
            </div>
            <nav className="p-3 space-y-4">
              {NAV_SECTIONS.map((section) => (
                <div key={section.title}>
                  <p className="text-[9px] font-semibold uppercase tracking-widest px-2 mb-1.5" style={{ color: "#525266" }}>
                    {section.title}
                  </p>
                  <div className="space-y-0.5">
                    {section.items.map((item) => (
                      <button
                        key={item.id}
                        onClick={() => {
                          onSectionChange(item.id);
                          onMobileClose();
                        }}
                        className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-[11px] transition-all text-left ${
                          activeSection === item.id
                            ? "bg-indigo-500/10 text-indigo-300"
                            : "text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.03]"
                        }`}
                      >
                        <item.icon size={13} className="shrink-0" />
                        {item.label}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </nav>
          </aside>
        </div>
      )}
    </>
  );
}

/* ─── Code Block ──────────────────────────────────────── */
function CodeBlock({ code, language = "bash" }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className="rounded-xl overflow-hidden my-6"
      style={{ border: "1px solid rgba(255,255,255,0.06)" }}
    >
      <div
        className="flex items-center justify-between px-4 py-2"
        style={{ background: "rgba(255,255,255,0.03)", borderBottom: "1px solid rgba(255,255,255,0.04)" }}
      >
        <span className="text-[10px] font-mono" style={{ color: "#525266" }}>{language}</span>
        <button
          onClick={handleCopy}
          className="text-[10px] flex items-center gap-1.5 px-2 py-1 rounded-md transition-all hover:bg-white/5"
          style={{ color: copied ? "#22c55e" : "#8b8b9e" }}
        >
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
      <pre
        className="p-4 overflow-x-auto text-xs leading-relaxed"
        style={{ background: "rgba(0,0,0,0.3)", color: "#e8e8ed" }}
      >
        <code className="font-mono">{code}</code>
      </pre>
    </div>
  );
}

/* ─── Content Renderer ────────────────────────────────── */
function ContentSection({ sectionId }: { sectionId: string }) {
  const data = SECTION_CONTENT[sectionId];
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [sectionId]);

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64" style={{ color: "#525266" }}>
        <Loader2 size={20} className="animate-spin" />
      </div>
    );
  }

  return (
    <div ref={ref} className="max-w-3xl animate-fade-in">
      <h1 className="text-2xl sm:text-3xl font-bold mb-6" style={{ color: "#e8e8ed" }}>
        {data.title}
      </h1>

      <div
        className="text-sm leading-relaxed space-y-4"
        style={{ color: "#8b8b9e" }}
      >
        {data.content.split("\n\n").map((paragraph, i) => {
          // Format headings within content
          if (paragraph.startsWith("Key capabilities:")) {
            return (
              <div key={i}>
                <p className="font-semibold mb-2" style={{ color: "#e8e8ed" }}>Key capabilities:</p>
                <ul className="space-y-1.5 ml-4">
                  {paragraph
                    .replace("Key capabilities:", "")
                    .trim()
                    .split("\n")
                    .filter((l) => l.trim())
                    .map((item, j) => (
                      <li key={j} className="flex items-start gap-2">
                        <span className="mt-[6px] w-1.5 h-1.5 rounded-full shrink-0" style={{ background: "#6366f1" }} />
                        <span>{item.replace(/^•\s*/, "")}</span>
                      </li>
                    ))}
                </ul>
              </div>
            );
          }

          // Format numbered lists
          if (paragraph.match(/^\d+\.\s/)) {
            return (
              <ol key={i} className="space-y-1.5 ml-4 list-decimal" style={{ color: "#8b8b9e" }}>
                {paragraph.split("\n").map((line, j) => {
                  const match = line.match(/^\d+\.\s(.+)$/);
                  if (match) return <li key={j} className="pl-1">{match[1]}</li>;
                  if (line.trim()) return <li key={j} className="pl-1">{line.trim()}</li>;
                  return null;
                })}
              </ol>
            );
          }

          // Format bullet lists
          if (paragraph.startsWith("•") || paragraph.startsWith("-")) {
            return (
              <ul key={i} className="space-y-1.5 ml-4">
                {paragraph.split("\n").map((line, j) => {
                  const text = line.replace(/^[-•]\s*/, "").trim();
                  if (!text) return null;
                  return (
                    <li key={j} className="flex items-start gap-2">
                      <span className="mt-[6px] w-1.5 h-1.5 rounded-full shrink-0" style={{ background: "#525266" }} />
                      <span>{text}</span>
                    </li>
                  );
                })}
              </ul>
            );
          }

          // Check for key: value pairs (config)
          if (paragraph.match(/^•\s*\*\*/)) {
            return (
              <ul key={i} className="space-y-1.5 ml-4">
                {paragraph.split("\n").map((line, j) => {
                  const clean = line.replace(/^•\s*/, "");
                  const parts = clean.split(/—\s*/);
                  if (parts.length > 1) {
                    return (
                      <li key={j} className="flex items-start gap-2 text-xs" style={{ color: "#8b8b9e" }}>
                        <span className="mt-[6px] w-1.5 h-1.5 rounded-full shrink-0" style={{ background: "#525266" }} />
                        <span>
                          <strong className="font-mono" style={{ color: "#a5b4fc" }}>{parts[0].replace(/\*\*/g, "")}</strong>
                          {parts[1] && <span> — {parts[1]}</span>}
                        </span>
                      </li>
                    );
                  }
                  return (
                    <li key={j} className="flex items-start gap-2">
                      <span className="mt-[6px] w-1.5 h-1.5 rounded-full shrink-0" style={{ background: "#525266" }} />
                      <span>{clean}</span>
                    </li>
                  );
                })}
              </ul>
            );
          }

          // Check for "Required:" / "Optional:" headings
          if (paragraph.startsWith("Required:") || paragraph.startsWith("Optional:")) {
            return (
              <div key={i}>
                <p className="font-semibold mb-2" style={{ color: "#e8e8ed" }}>
                  {paragraph.startsWith("Required:") ? "Required:" : "Optional:"}
                </p>
                <ul className="space-y-1.5 ml-4">
                  {paragraph
                    .replace(/^(Required|Optional):/, "")
                    .trim()
                    .split("\n")
                    .filter((l) => l.trim())
                    .map((item, j) => {
                      const clean = item.replace(/^•\s*/, "").trim();
                      const parts = clean.split(/—\s*/);
                      return (
                        <li key={j} className="flex items-start gap-2 text-xs" style={{ color: "#8b8b9e" }}>
                          <span className="mt-[6px] w-1.5 h-1.5 rounded-full shrink-0" style={{ background: "#525266" }} />
                          <span>
                            {parts[0] && <strong className="font-mono" style={{ color: "#a5b4fc" }}>{parts[0]}</strong>}
                            {parts[1] && <span> — {parts[1]}</span>}
                          </span>
                        </li>
                      );
                    })}
                </ul>
              </div>
            );
          }

          // Check for subsections like "1. Claim Extraction — ..."
          if (paragraph.match(/^\d+\.\s[^(]*—/)) {
            return (
              <div key={i} className="space-y-2">
                {paragraph.split("\n").map((line, j) => {
                  const match = line.match(/^(\d+\.\s[^—]*)—(.+)$/);
                  if (match) {
                    return (
                      <div key={j} className="flex items-start gap-3">
                        <span className="w-5 h-5 rounded flex items-center justify-center text-[9px] font-bold shrink-0 mt-0.5" style={{ background: "rgba(99,102,241,0.1)", color: "#a5b4fc" }}>
                          {match[1].split(".")[0]}
                        </span>
                        <div>
                          <strong className="text-xs" style={{ color: "#e8e8ed" }}>{match[1].replace(/^\d+\.\s*/, "")}</strong>
                          <span className="text-xs"> — {match[2]}</span>
                        </div>
                      </div>
                    );
                  }
                  return <p key={j} className="text-xs">{line}</p>;
                })}
              </div>
            );
          }

          return <p key={i}>{paragraph}</p>;
        })}
      </div>

      {data.code && <CodeBlock code={data.code} />}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   MAIN PAGE
   ═══════════════════════════════════════════════════════ */
export default function DocsPage() {
  const [activeSection, setActiveSection] = useState("introduction");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [showScrollTop, setShowScrollTop] = useState(false);

  useEffect(() => {
    const onScroll = () => setShowScrollTop(window.scrollY > 400);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="min-h-screen" style={{ background: "#0a0a0f" }}>
      {/* Mobile Top Bar */}
      <div
        className="md:hidden fixed top-0 left-0 right-0 z-40 flex items-center justify-between px-4 h-14"
        style={{
          background: "rgba(10,10,15,0.95)",
          borderBottom: "1px solid rgba(255,255,255,0.04)",
          backdropFilter: "blur(20px)",
        }}
      >
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setMobileNavOpen(true)}
            className="p-1.5 rounded-lg hover:bg-white/5"
            style={{ color: "#8b8b9e" }}
          >
            <MenuIcon size={18} />
          </button>
          <div className="w-6 h-6 rounded-lg flex items-center justify-center" style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}>
            <BookOpen size={11} className="text-white" />
          </div>
          <span className="text-xs font-semibold" style={{ color: "#e8e8ed" }}>Documentation</span>
        </div>
        <a
          href="/"
          className="text-[10px] flex items-center gap-1 px-2.5 py-1.5 rounded-lg transition-all"
          style={{ color: "#8b8b9e", background: "rgba(255,255,255,0.03)" }}
        >
          Home
        </a>
      </div>

      <div className="flex pt-14 md:pt-0">
        <DocsSidebar
          activeSection={activeSection}
          onSectionChange={setActiveSection}
          mobileOpen={mobileNavOpen}
          onMobileClose={() => setMobileNavOpen(false)}
        />

        {/* Main Content */}
        <main className="flex-1 min-h-screen">
          <div className="max-w-4xl mx-auto px-5 md:px-12 py-8 md:py-16">
            {/* Breadcrumb */}
            <div className="flex items-center gap-1.5 text-[10px] mb-8" style={{ color: "#525266" }}>
              <a href="/" className="hover:text-indigo-400 transition-colors">Home</a>
              <ChevronRight size={10} />
              <span style={{ color: "#8b8b9e" }}>Documentation</span>
              <ChevronRight size={10} />
              <span style={{ color: "#a5b4fc" }}>{SECTION_CONTENT[activeSection]?.title}</span>
            </div>

            <ContentSection sectionId={activeSection} />
          </div>
        </main>
      </div>

      {/* Scroll to Top */}
      {showScrollTop && (
        <button
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          className="fixed bottom-6 right-6 w-10 h-10 rounded-xl flex items-center justify-center z-40 transition-all hover:shadow-lg"
          style={{
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            color: "#fff",
            boxShadow: "0 4px 16px rgba(99,102,241,0.3)",
          }}
        >
          <ArrowUp size={16} />
        </button>
      )}
    </div>
  );
}