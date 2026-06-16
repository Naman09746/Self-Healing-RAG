"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import {
  Brain,
  MessageSquare,
  Send,
  Loader2,
  CheckCircle,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  FileText,
  Copy,
  ThumbsUp,
  ThumbsDown,
  Clock,
  Shield,
  Zap,
  RefreshCw,
  BookOpen,
  Settings,
  LogOut,
  Sparkles,
  BarChart3,
  ChevronRight,
  TrendingUp,
  Activity,
  PieChart,
  Search,
  PanelRightOpen,
  PanelRightClose,
  Trash2,
  Upload,
  Globe,
  Network,
  GitBranch,
  Mail,
  ExternalLink,
  ArrowRight,
  Gauge,
  Layers,
  Bot,
} from "lucide-react";
import { clearTokens, type DocumentInfo, type MetricsSnapshot } from "@/lib/api";
import { useQuery, useDocuments, useHealth, useMetrics, useAuth } from "@/lib/hooks";
import SystemStatus from "@/components/SystemStatus";
import LivePipeline from "@/components/LivePipeline";

/* ─── Types ──────────────────────────────────────────── */
interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  confidence?: number;
  sources?: { title: string; score: number }[];
  verified?: boolean;
  timestamp: number;
  groundingScore?: number;
  latency?: number;
}

interface PipelinePhase {
  id: string;
  label: string;
  status: "idle" | "active" | "done" | "error";
}

/* ─── Mock Queries ───────────────────────────────────── */
const MOCK_QUERIES = [
  "What are the key findings from Q4 strategic intelligence?",
  "Summarize the project omega specifications",
  "How does the hallucination detection system work?",
  "Explain the multi-agent RAG pipeline architecture",
];

/* ─── Sparkline ───────────────────────────────────────── */
function SparkLine({ data, color = "#6366f1", height = 28 }: { data: number[]; color?: string; height?: number }) {
  const max = Math.max(...data, 1);
  const w = 60;
  const points = data.map((v, i) => `${(i / (data.length - 1)) * w},${height - (v / max) * height}`).join(" ");
  return (
    <svg width={w} height={height} className="shrink-0">
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity={0.8} />
      <polygon points={points + ` ${w},${height} 0,${height}`} fill={`${color}10`} />
    </svg>
  );
}

/* ═══════════════════════════════════════════════════════
   TOP NAV BAR
   ═══════════════════════════════════════════════════════ */
function TopNav() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className="flex items-center justify-between h-12 px-4 shrink-0 transition-all duration-200"
      style={{
        background: scrolled ? "var(--bg-glass-strong)" : "transparent",
        borderBottom: "1px solid rgba(255,255,255,0.04)",
        backdropFilter: scrolled ? "blur(16px)" : "none",
      }}
    >
      {/* Left — Brand */}
      <div className="flex items-center gap-3">
        <Link href="/" className="flex items-center gap-2 group">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center transition-all duration-200 group-hover:shadow-lg"
            style={{ background: "linear-gradient(135deg, #6366f1, #a855f7)" }}
          >
            <Brain size={14} className="text-white" />
          </div>
          <span className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
            Nexus Core
          </span>
          <span className="text-[9px] font-mono px-1 py-0.5 rounded" style={{ background: "rgba(255,255,255,0.03)", color: "var(--text-muted)" }}>
            v2.0
          </span>
        </Link>

        {/* Nav Links */}
        <nav className="hidden md:flex items-center ml-6 gap-0.5">
          {[
            { href: "/dashboard", label: "Live", icon: Activity, active: true },
            { href: "/docs", label: "Docs", icon: BookOpen },
            { href: "/settings", label: "Settings", icon: Settings },
          ].map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all"
              style={{
                color: item.active ? "var(--text-accent)" : "var(--text-muted)",
                background: item.active ? "rgba(99,102,241,0.06)" : "transparent",
              }}
            >
              <item.icon size={12} />
              {item.label}
            </Link>
          ))}
        </nav>
      </div>

      {/* Right — Status + Theme + User */}
      <div className="flex items-center gap-3">
        <SystemStatus />
        <ThemeToggle />
        <div className="w-px h-4" style={{ background: "var(--border-default)" }} />
        <button
          onClick={() => {
            clearTokens();
            window.location.href = "/auth";
          }}
          className="flex items-center gap-1.5 px-2 py-1 rounded-lg text-[10px] font-medium transition-all hover:bg-white/[0.04]"
          style={{ color: "var(--text-muted)" }}
        >
          <LogOut size={12} />
          Sign out
        </button>
      </div>
    </header>
  );
}

/* ═══════════════════════════════════════════════════════
   METRICS BAR
   ═══════════════════════════════════════════════════════ */
const METRIC_TRENDS: Record<string, number[]> = {
  confidence: [91, 93, 92, 95, 94, 96, 97, 95, 98, 97, 96, 97],
  latency: [280, 260, 310, 240, 230, 220, 245, 235, 225, 240, 230, 240],
  healing: [2, 3, 1, 4, 2, 5, 3, 2, 1, 3, 2, 3],
};

function MetricsBar({ metricsSnapshot }: { metricsSnapshot?: MetricsSnapshot | null }) {
  const m = metricsSnapshot;
  const items = [
    {
      label: "Avg. Confidence",
      value: m?.avg_grounding_score ? `${(m.avg_grounding_score * 100).toFixed(1)}%` : "—",
      icon: Shield,
      color: "#22c55e",
      trend: METRIC_TRENDS.confidence,
    },
    {
      label: "Avg. Latency",
      value: m?.avg_latency_ms ? `${m.avg_latency_ms}ms` : "—",
      icon: Zap,
      color: "#f59e0b",
      trend: METRIC_TRENDS.latency,
    },
    {
      label: "Queries Total",
      value: m?.queries_total ? m.queries_total.toLocaleString() : "—",
      icon: MessageSquare,
      color: "#818cf8",
      trend: METRIC_TRENDS.confidence,
    },
    {
      label: "Self-Heals",
      value: m?.healings_total ? m.healings_total.toLocaleString() : "—",
      icon: RefreshCw,
      color: "#06b6d4",
      trend: METRIC_TRENDS.healing,
    },
  ];

  return (
    <div className="grid grid-cols-4 gap-2">
      {items.map((item) => (
        <div
          key={item.label}
          className="rounded-lg p-2.5 transition-all hover:bg-white/[0.02]"
          style={{ background: "rgba(255,255,255,0.01)", border: "1px solid rgba(255,255,255,0.04)" }}
        >
          <div className="flex items-center gap-1.5 mb-1.5">
            <item.icon size={10} style={{ color: item.color }} />
            <span className="text-[9px] font-medium" style={{ color: "var(--text-muted)" }}>
              {item.label}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold font-mono" style={{ color: "var(--text-primary)" }}>
              {item.value}
            </span>
            <SparkLine data={item.trend} color={item.color} height={20} />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   CHAT PANEL
   ═══════════════════════════════════════════════════════ */
function ChatPanel({
  activePhase,
  phaseStatus,
  onQueryStart,
  onQueryComplete,
}: {
  activePhase: string | null;
  phaseStatus: Record<string, PipelinePhase["status"]>;
  onQueryStart?: () => void;
  onQueryComplete?: (result: { confidence: number; groundingScore: number; latency: number; verified: boolean }) => void;
}) {
  const { ask, askStream, cancel, processing, streaming, lastResponse } = useQuery();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "I'm your self-healing knowledge assistant. Ask me anything about your documents — I'll retrieve, verify, and cite every claim.",
      timestamp: Date.now(),
      verified: true,
    },
  ]);
  const [input, setInput] = useState("");
  const [showExamples, setShowExamples] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const sessionIdRef = useRef(`sess_${Date.now()}`);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const handleSend = async () => {
    const q = input.trim();
    if (!q || processing || streaming) return;
    setInput("");
    setShowExamples(false);

    const userMsg: Message = { id: `user-${Date.now()}`, role: "user", content: q, timestamp: Date.now() };
    setMessages((prev) => [...prev, userMsg]);
    onQueryStart?.();

    const startTime = Date.now();

    try {
      const response = await ask(q, sessionIdRef.current);

      if (response) {
        const elapsed = Date.now() - startTime;

        const assistantMsg: Message = {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: response.answer,
          confidence: response.grounding_score * 100,
          sources: response.sources.map((s) => ({
            title: s.source,
            score: s.score,
          })),
          verified: !response.is_hallucinated,
          timestamp: Date.now(),
          groundingScore: response.grounding_score,
          latency: elapsed,
        };

        setMessages((prev) => [...prev, assistantMsg]);

        onQueryComplete?.({
          confidence: response.grounding_score * 100,
          groundingScore: response.grounding_score,
          latency: elapsed,
          verified: !response.is_hallucinated,
        });
      }
    } catch (err) {
      const errorMsg: Message = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: `**Error processing query:** ${(err as Error).message || "Unknown error"}\n\nPlease check that the backend is running and try again.`,
        timestamp: Date.now(),
        verified: false,
        confidence: 0,
      };
      setMessages((prev) => [...prev, errorMsg]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3 scroll-smooth">
        {/* Examples */}
        {showExamples && (
          <div className="mb-3 animate-fade-in">
            <p className="text-[9px] font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
              Try asking
            </p>
            <div className="flex flex-wrap gap-1.5">
              {MOCK_QUERIES.map((q) => (
                <button
                  key={q}
                  onClick={() => { setInput(q); setShowExamples(false); }}
                  className="text-[10px] px-2.5 py-1.5 rounded-lg transition-all hover:bg-indigo-500/8 hover:text-indigo-300"
                  style={{
                    background: "rgba(255,255,255,0.02)",
                    border: "1px solid rgba(255,255,255,0.05)",
                    color: "var(--text-secondary)",
                  }}
                >
                  {q.length > 55 ? q.slice(0, 55) + "…" : q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} animate-fade-in`}>
            <div
              className={`max-w-[85%] rounded-xl ${
                msg.role === "user"
                  ? "px-3.5 py-2.5"
                  : "p-3"
              }`}
              style={{
                background: msg.role === "user" ? "rgba(99,102,241,0.06)" : "rgba(255,255,255,0.02)",
                border: `1px solid ${msg.role === "user" ? "rgba(99,102,241,0.12)" : "rgba(255,255,255,0.04)"}`,
              }}
            >
              {/* Assistant header */}
              {msg.role === "assistant" && (
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-4 h-4 rounded flex items-center justify-center" style={{ background: "linear-gradient(135deg, #6366f1, #a855f7)" }}>
                    <Brain size={8} className="text-white" />
                  </div>
                  <span className="text-[9px] font-semibold" style={{ color: "var(--text-accent)" }}>Nexus Core</span>
                  {msg.verified !== undefined && (
                    <span
                      className="text-[8px] flex items-center gap-1 px-1.5 py-0.5 rounded-full font-medium"
                      style={{
                        background: msg.verified ? "rgba(34,197,94,0.08)" : "rgba(245,158,11,0.08)",
                        color: msg.verified ? "#22c55e" : "#f59e0b",
                      }}
                    >
                      {msg.verified ? <CheckCircle size={7} /> : <AlertCircle size={7} />}
                      {msg.verified ? "Verified" : "Low Confidence"}
                    </span>
                  )}
                </div>
              )}

              {/* Content */}
              <div
                className="text-[11px] leading-relaxed"
                style={{ color: msg.role === "user" ? "var(--text-primary)" : "var(--text-secondary)" }}
                dangerouslySetInnerHTML={{
                  __html: msg.content
                    .replace(/\*\*(.*?)\*\*/g, "<strong style='color:#f0f0f5'>$1</strong>")
                    .replace(/\n/g, "<br/>"),
                }}
              />

              {/* Sources */}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-2.5 pt-2 space-y-1" style={{ borderTop: "1px solid rgba(255,255,255,0.03)" }}>
                  <p className="text-[8px] font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Sources</p>
                  {msg.sources.map((s, i) => (
                    <div key={i} className="flex items-center gap-1.5 text-[9px]" style={{ color: "var(--text-secondary)" }}>
                      <FileText size={8} />
                      <span className="flex-1 truncate">{s.title}</span>
                      <span className="font-mono" style={{ color: "var(--text-accent)" }}>{Math.round(s.score * 100)}%</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Confidence bar + actions */}
              {msg.role === "assistant" && msg.confidence && (
                <div className="flex items-center gap-2 mt-2 pt-2" style={{ borderTop: "1px solid rgba(255,255,255,0.02)" }}>
                  <div className="flex-1 flex items-center gap-1.5">
                    <div className="flex-1 h-1 rounded-full bg-white/[0.04] overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-1000"
                        style={{
                          width: `${msg.confidence}%`,
                          background: msg.confidence > 85
                            ? "linear-gradient(90deg, #10b981, #22c55e)"
                            : "linear-gradient(90deg, #f59e0b, #ef4444)",
                        }}
                      />
                    </div>
                    <span className="text-[8px] font-mono" style={{ color: "var(--text-muted)" }}>{msg.confidence}%</span>
                  </div>
                  {msg.groundingScore !== undefined && (
                    <span className="text-[8px] font-mono" style={{ color: "var(--text-muted)" }}>
                      G: {msg.groundingScore.toFixed(2)}
                    </span>
                  )}
                  {msg.latency && (
                    <span className="text-[8px] font-mono" style={{ color: "var(--text-muted)" }}>
                      {msg.latency}ms
                    </span>
                  )}
                  <div className="flex items-center gap-0.5 ml-1">
                    <button className="p-0.5 rounded hover:bg-white/5 transition-colors" style={{ color: "var(--text-muted)" }}><Copy size={8} /></button>
                    <button className="p-0.5 rounded hover:bg-white/5 transition-colors" style={{ color: "var(--text-muted)" }}><ThumbsUp size={8} /></button>
                    <button className="p-0.5 rounded hover:bg-white/5 transition-colors" style={{ color: "var(--text-muted)" }}><ThumbsDown size={8} /></button>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {processing && (
          <div className="flex justify-start animate-fade-in">
            <div className="px-3 py-2.5 rounded-xl" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)" }}>
              <div className="flex items-center gap-2">
                <Loader2 size={10} className="animate-spin" style={{ color: "#818cf8" }} />
                <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>Processing through pipeline…</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3" style={{ borderTop: "1px solid rgba(255,255,255,0.04)" }}>
        <div
          className="flex items-end gap-2 px-3 py-2 rounded-xl transition-all duration-200"
          style={{
            background: "rgba(255,255,255,0.02)",
            border: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about your knowledge base…"
            rows={1}
            className="flex-1 bg-transparent border-none outline-none resize-none text-xs text-white placeholder-zinc-600"
            style={{ fontFamily: "var(--font-sans)", maxHeight: "80px" }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || processing}
            className="w-7 h-7 rounded-lg flex items-center justify-center transition-all shrink-0"
            style={{
              background: input.trim() && !processing ? "linear-gradient(135deg, #6366f1, #a855f7)" : "rgba(255,255,255,0.04)",
              color: input.trim() && !processing ? "#fff" : "#333",
            }}
          >
            {processing ? <Loader2 size={11} className="animate-spin" /> : <Send size={11} />}
          </button>
        </div>
        <p className="text-[8px] mt-1 text-center" style={{ color: "#333" }}>
          Every response is verified through the multi-agent pipeline — grounding scores and source citations provided
        </p>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   DOCUMENTS PANEL (collapsible)
   ═══════════════════════════════════════════════════════ */
function DocumentsPanel() {
  const [expanded, setExpanded] = useState(false);
  const { documents, loading, uploading, upload, remove, refresh } = useDocuments();
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <div
      className="shrink-0 transition-all duration-200 overflow-hidden"
      style={{
        borderTop: "1px solid rgba(255,255,255,0.04)",
        background: "rgba(255,255,255,0.01)",
        maxHeight: expanded ? "240px" : "36px",
      }}
    >
      {/* Toggle Bar */}
      <div
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-2 transition-all hover:bg-white/[0.02] cursor-pointer"
      >
        <div className="flex items-center gap-2">
          <FileText size={11} style={{ color: "var(--text-muted)" }} />
          <span className="text-[10px] font-medium" style={{ color: "var(--text-secondary)" }}>
            Documents
          </span>
          <span className="text-[9px] font-mono px-1 py-0.5 rounded" style={{ background: "rgba(99,102,241,0.06)", color: "var(--text-accent)" }}>
            {documents.length} indexed
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              fileInputRef.current?.click();
            }}
            disabled={uploading}
            className="btn text-[9px] px-2 py-1"
            style={{ border: "1px solid rgba(255,255,255,0.06)", color: "var(--text-secondary)", background: "transparent", borderRadius: "6px" }}
          >
            <Upload size={9} /> {uploading ? "Uploading…" : "Upload"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.doc,.txt,.md"
            className="hidden"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (file) { await upload(file); e.target.value = ""; }
            }}
          />
          {expanded ? <ChevronDown size={12} style={{ color: "var(--text-muted)" }} /> : <ChevronUp size={12} style={{ color: "var(--text-muted)" }} />}
        </div>
      </div>

      {/* Document List */}
      <div className="px-4 pb-3 space-y-1.5">
        {loading && documents.length === 0 && (
          <div className="flex items-center justify-center py-4">
            <Loader2 size={12} className="animate-spin" style={{ color: "var(--text-muted)" }} />
          </div>
        )}
        {!loading && documents.length === 0 && (
          <div className="text-center py-4">
            <p className="text-[10px]" style={{ color: "var(--text-muted)" }}>No documents indexed yet. Upload a PDF, DOCX, or TXT file to get started.</p>
          </div>
        )}
        {documents.map((doc) => (
          <div
            key={doc.id}
            className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg transition-all hover:bg-white/[0.02]"
          >
            <div className="w-6 h-6 rounded flex items-center justify-center" style={{ background: "rgba(99,102,241,0.06)" }}>
              <FileText size={10} style={{ color: "var(--text-accent)" }} />
            </div>
            <div className="flex-1 min-w-0 flex items-center gap-2">
              <span className="text-[10px] font-medium truncate" style={{ color: "var(--text-secondary)" }}>{doc.filename}</span>
              <span className="text-[8px] px-1 py-0.5 rounded-full font-medium" style={{
                background: doc.status === "indexed" ? "rgba(34,197,94,0.08)" : doc.status === "processing" ? "rgba(245,158,11,0.08)" : "rgba(239,68,68,0.08)",
                color: doc.status === "indexed" ? "#22c55e" : doc.status === "processing" ? "#f59e0b" : "#ef4444",
              }}>
                {doc.status}
              </span>
            </div>
            <span className="text-[8px]" style={{ color: "var(--text-muted)" }}>{doc.chunks} chunks</span>
            <span className="text-[8px]" style={{ color: "var(--text-muted)" }}>{doc.created_at?.split("T")[0]}</span>
            <button
              onClick={() => remove(doc.id)}
              className="p-0.5 rounded hover:bg-white/5 transition-colors"
              style={{ color: "var(--text-muted)" }}
            >
              <Trash2 size={9} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   MAIN DASHBOARD — Unified Live View
   ═══════════════════════════════════════════════════════ */
export default function DashboardPage() {
  const [activePhase, setActivePhase] = useState<string | null>(null);
  const { metrics } = useMetrics(30000);
  const { authenticated } = useAuth();
  const { status: healthStatus } = useHealth(30000);

  // Redirect to auth if not authenticated
  useEffect(() => {
    if (!authenticated && !localStorage.getItem("rag_access_token")) {
      // Allow unauthenticated access in dev mode — backend is local
    }
  }, [authenticated]);

  const handleQueryStart = useCallback(() => {
    setActivePhase("intake");
  }, []);

  const handleQueryComplete = useCallback((result: { confidence: number; groundingScore: number; latency: number; verified: boolean }) => {
    setActivePhase(null);
  }, []);

  return (
    <div className="h-screen flex flex-col" style={{ background: "var(--bg-base)" }}>
      <TopNav />

      {/* Main Content — Split Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* ── Left Panel: Chat ── */}
        <div className="flex-1 flex flex-col min-w-0" style={{ borderRight: "1px solid rgba(255,255,255,0.04)" }}>
          <ChatPanel
            activePhase={activePhase}
            phaseStatus={{}}
            onQueryStart={handleQueryStart}
            onQueryComplete={handleQueryComplete}
          />
        </div>

        {/* ── Right Panel: Pipeline + Metrics ── */}
        <div className="w-[380px] xl:w-[420px] flex flex-col shrink-0">
          {/* Section Label */}
          <div className="flex items-center gap-2 px-3 py-2" style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
            <Layers size={11} style={{ color: "#818cf8" }} />
            <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
              Live Pipeline
            </span>
            {activePhase && (
              <span className="text-[9px] font-mono ml-auto" style={{ color: "#818cf8" }}>
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse mr-1" />
                {activePhase}
              </span>
            )}
            {healthStatus && (
              <span className="text-[9px] font-mono" style={{ color: healthStatus.status === "healthy" ? "#22c55e" : "#ef4444" }}>
                <span className="inline-block w-1.5 h-1.5 rounded-full mr-1" style={{
                  background: healthStatus.status === "healthy" ? "#22c55e" : "#ef4444",
                }} />
                API
              </span>
            )}
          </div>

          {/* Pipeline Graph */}
          <div className="flex-1 min-h-0">
            <LivePipeline activePhase={activePhase} phaseStatus={{}} />
          </div>

          {/* Metrics Bar */}
          <div className="px-3 py-2" style={{ borderTop: "1px solid rgba(255,255,255,0.04)", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
            <div className="flex items-center gap-2 mb-2">
              <BarChart3 size={10} style={{ color: "var(--text-muted)" }} />
              <span className="text-[9px] font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Metrics</span>
            </div>
            <MetricsBar metricsSnapshot={metrics} />
          </div>

          {/* Health Status */}
          <div className="flex items-center gap-2 px-3 py-2">
            <Activity size={10} style={{ color: "var(--text-muted)" }} />
            <span className="text-[9px] font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>System</span>
            <SystemStatus />
          </div>
        </div>
      </div>

      {/* ── Bottom Panel: Documents ── */}
      <DocumentsPanel />
    </div>
  );
}
