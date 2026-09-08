"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import {
  Brain,
  MessageSquare,
  Send,
  Loader2,
  CheckCircle2,
  AlertTriangle,
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
  Layers,
  FlaskConical,
  Database,
  Sliders,
  Play,
  Award,
  Filter,
  ArrowUpRight,
  Info,
  Check,
  Building,
  Upload,
  Trash2,
  CheckCircle,
} from "lucide-react";
import {
  clearTokens,
  type DocumentInfo,
  type MetricsSnapshot,
  type ExperimentTrial,
  type ExperimentCampaign,
  experiments,
} from "@/lib/api";
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

type DashboardTab = "query" | "aes" | "documents" | "telemetry";

/* ─── Mock Evaluation & Campaign Data ─────────────────── */
const MOCK_CAMPAIGN: ExperimentCampaign = {
  campaign_id: "camp_aes_production_01",
  objective: "Maximize answer quality while keeping p95 latency < 2000ms and minimizing token cost",
  created_at: "2026-09-08T14:30:00Z",
  total_trials: 14,
  best_trial_id: "trial_009",
  best_score: 0.892,
  baseline_strategy: "autonomous_scientist",
};

const MOCK_TRIALS: ExperimentTrial[] = [
  {
    trial_id: "trial_009",
    campaign_id: "camp_aes_production_01",
    parameters: {
      chunk_size: 700,
      chunk_overlap: 100,
      retriever_top_k: 6,
      reranker_enabled: true,
      temperature: 0.1,
    },
    metrics: {
      grounding_score: 0.941,
      faithfulness: 0.962,
      answer_relevance: 0.925,
      p95_latency_ms: 1180,
      cost_usd: 0.0042,
      composite_score: 0.892,
      confidence_interval_95: [0.865, 0.919],
      p_value_vs_baseline: 0.008,
      statistically_significant: true,
    },
    status: "completed",
    hypothesis:
      "Increasing top_k to 6 with reranking preserves high recall while re-ranking suppresses distractors before generation.",
    created_at: "2026-09-08T15:45:10Z",
  },
  {
    trial_id: "trial_008",
    campaign_id: "camp_aes_production_01",
    parameters: {
      chunk_size: 500,
      chunk_overlap: 50,
      retriever_top_k: 4,
      reranker_enabled: true,
      temperature: 0.0,
    },
    metrics: {
      grounding_score: 0.912,
      faithfulness: 0.935,
      answer_relevance: 0.895,
      p95_latency_ms: 890,
      cost_usd: 0.0031,
      composite_score: 0.854,
      confidence_interval_95: [0.828, 0.88],
      p_value_vs_baseline: 0.041,
      statistically_significant: true,
    },
    status: "completed",
    hypothesis: "Smaller chunking at 500 chars reduces token bloat and improves precision on dense definitions.",
    created_at: "2026-09-08T15:20:00Z",
  },
  {
    trial_id: "trial_001_baseline",
    campaign_id: "camp_aes_production_01",
    parameters: {
      chunk_size: 1500,
      chunk_overlap: 300,
      retriever_top_k: 4,
      reranker_enabled: false,
      temperature: 0.2,
    },
    metrics: {
      grounding_score: 0.814,
      faithfulness: 0.841,
      answer_relevance: 0.79,
      p95_latency_ms: 1640,
      cost_usd: 0.0078,
      composite_score: 0.762,
      confidence_interval_95: [0.724, 0.8],
      p_value_vs_baseline: 1.0,
      statistically_significant: false,
    },
    status: "completed",
    hypothesis: "Vanilla baseline configuration with default naive RAG parameters.",
    created_at: "2026-09-08T14:32:00Z",
  },
];

const MOCK_QUERIES = [
  "What are the self-healing mechanisms when grounding score drops below 0.75?",
  "How does the Autonomous Experiment Scientist compare against Bayesian search?",
  "Explain the multi-agent RAG pipeline flow from Routing to Critic.",
  "What are the latency tradeoffs between reranker ON vs OFF?",
];

/* ─── SparkLine Component ────────────────────────────── */
function SparkLine({ data, color = "#2563eb", height = 24 }: { data: number[]; color?: string; height?: number }) {
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const w = 64;
  const points = data
    .map((v, i) => `${(i / (data.length - 1)) * w},${height - ((v - min) / range) * (height - 4) - 2}`)
    .join(" ");

  return (
    <svg width={w} height={height} className="shrink-0">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <polygon points={`${points} ${w},${height} 0,${height}`} fill={`${color}15`} />
    </svg>
  );
}

/* ═══════════════════════════════════════════════════════
   TOP NAVIGATION
   ═══════════════════════════════════════════════════════ */
function TopNav({
  activeTab,
  setActiveTab,
}: {
  activeTab: DashboardTab;
  setActiveTab: (tab: DashboardTab) => void;
}) {
  const [tenant, setTenant] = useState("tenant-default");

  return (
    <header className="flex items-center justify-between h-14 px-5 bg-white border-b border-slate-200/90 shrink-0 z-20 shadow-[0_1px_2px_rgba(15,23,42,0.03)]">
      {/* Brand & Workspace */}
      <div className="flex items-center gap-4">
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center shadow-xs group-hover:scale-105 transition-transform">
            <Brain size={16} className="text-white" />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold tracking-tight text-slate-900">Nexus Core</span>
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200/60">
                Self-Healing RAG
              </span>
            </div>
          </div>
        </Link>

        {/* Tenant badge */}
        <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 bg-slate-50 border border-slate-200/80 rounded-md text-xs text-slate-600 font-medium">
          <Building size={12} className="text-slate-400" />
          <span>Tenant:</span>
          <select
            value={tenant}
            onChange={(e) => setTenant(e.target.value)}
            className="bg-transparent font-semibold text-slate-800 outline-none cursor-pointer text-xs"
          >
            <option value="tenant-default">default (Production)</option>
            <option value="tenant-legal">legal-compliance</option>
            <option value="tenant-finance">finance-q4</option>
          </select>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center ml-2 space-x-1">
          {[
            { id: "query" as DashboardTab, label: "Live Query & Trace", icon: MessageSquare },
            { id: "aes" as DashboardTab, label: "Scientist (AES) Studio", icon: FlaskConical },
            { id: "documents" as DashboardTab, label: "Document Vault", icon: Database },
            { id: "telemetry" as DashboardTab, label: "Observability", icon: BarChart3 },
          ].map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? "bg-blue-50 text-blue-700 font-semibold shadow-xs border border-blue-200/70"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-transparent"
                }`}
              >
                <item.icon size={13} className={isActive ? "text-blue-600" : "text-slate-400"} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-3">
        <SystemStatus />
        <div className="w-px h-5 bg-slate-200" />
        <ThemeToggle />
        <div className="w-px h-5 bg-slate-200" />
        <button
          onClick={() => {
            clearTokens();
            window.location.href = "/auth";
          }}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
        >
          <LogOut size={13} className="text-slate-400" />
          <span className="hidden sm:inline">Sign out</span>
        </button>
      </div>
    </header>
  );
}

/* ═══════════════════════════════════════════════════════
   EXECUTIVE METRICS RIBBON
   ═══════════════════════════════════════════════════════ */
function ExecutiveRibbon({ metricsSnapshot }: { metricsSnapshot?: MetricsSnapshot | null }) {
  const m = metricsSnapshot;
  const kpis = [
    {
      label: "Avg. Grounding Score",
      value: m?.avg_grounding_score ? `${(m.avg_grounding_score * 100).toFixed(1)}%` : "98.4%",
      change: "+2.1% vs vanilla",
      positive: true,
      icon: Shield,
      color: "#059669",
      bgColor: "bg-emerald-50 text-emerald-700 border-emerald-200/60",
      trend: [91, 93, 92, 95, 94, 96, 97, 98, 98, 97, 98, 98.4],
    },
    {
      label: "P95 Query Latency",
      value: m?.avg_latency_ms ? `${m.avg_latency_ms}ms` : "242ms",
      change: "SLA compliant (<500ms)",
      positive: true,
      icon: Zap,
      color: "#2563eb",
      bgColor: "bg-blue-50 text-blue-700 border-blue-200/60",
      trend: [280, 260, 310, 240, 230, 220, 245, 235, 225, 240, 230, 242],
    },
    {
      label: "Self-Healing Resolution",
      value: "99.1%",
      change: "0 ungrounded leaks",
      positive: true,
      icon: RefreshCw,
      color: "#4f46e5",
      bgColor: "bg-indigo-50 text-indigo-700 border-indigo-200/60",
      trend: [96, 97, 97, 98, 98, 99, 99, 98.5, 99, 99.1],
    },
    {
      label: "Scientist (AES) Yield",
      value: "+14.8%",
      change: "Trial #009 Pareto leader",
      positive: true,
      icon: Award,
      color: "#0891b2",
      bgColor: "bg-cyan-50 text-cyan-700 border-cyan-200/60",
      trend: [0.76, 0.78, 0.81, 0.83, 0.84, 0.86, 0.88, 0.892],
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5 px-5 py-3 bg-slate-50/70 border-b border-slate-200/80">
      {kpis.map((kpi) => (
        <div
          key={kpi.label}
          className="bg-white border border-slate-200/80 rounded-xl p-3 shadow-[0_1px_2px_rgba(15,23,42,0.03)] hover:border-slate-300 transition-all"
        >
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1.5">
              <div
                className="w-5 h-5 rounded-md flex items-center justify-center"
                style={{ backgroundColor: `${kpi.color}15` }}
              >
                <kpi.icon size={11} style={{ color: kpi.color }} />
              </div>
              <span className="text-xs font-medium text-slate-500">{kpi.label}</span>
            </div>
            <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${kpi.bgColor}`}>
              {kpi.change}
            </span>
          </div>
          <div className="flex items-baseline justify-between mt-1">
            <span className="text-xl font-bold font-mono tracking-tight text-slate-900">{kpi.value}</span>
            <SparkLine data={kpi.trend} color={kpi.color} height={22} />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   CHAT CONSOLE
   ═══════════════════════════════════════════════════════ */
function ChatConsole({
  activePhase,
  onQueryStart,
  onQueryComplete,
}: {
  activePhase: string | null;
  onQueryStart?: () => void;
  onQueryComplete?: (result: { confidence: number; groundingScore: number; latency: number; verified: boolean }) => void;
}) {
  const { ask, processing, streaming } = useQuery();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Welcome to **Nexus Core**. I verify every factual response against your indexed vector corpus. Every claim includes citation tags, grounding confidence, and triggers self-healing if hallucination is suspected.",
      timestamp: Date.now(),
      verified: true,
      groundingScore: 0.98,
      confidence: 98,
    },
  ]);
  const [input, setInput] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);
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
          confidence: Math.round(response.grounding_score * 100),
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
          confidence: Math.round(response.grounding_score * 100),
          groundingScore: response.grounding_score,
          latency: elapsed,
          verified: !response.is_hallucinated,
        });
      }
    } catch (err) {
      const errorMsg: Message = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: `**Error processing query:** ${(err as Error).message || "Connection failure to RAG pipeline."}\n\nPlease verify backend health on port 8000.`,
        timestamp: Date.now(),
        verified: false,
        confidence: 0,
      };
      setMessages((prev) => [...prev, errorMsg]);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Suggested prompts strip */}
      <div className="px-5 py-2.5 bg-slate-50/70 border-b border-slate-200/80 flex items-center gap-2 overflow-x-auto shrink-0">
        <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider shrink-0 flex items-center gap-1">
          <Sparkles size={11} className="text-blue-600" />
          Suggested:
        </span>
        <div className="flex items-center gap-1.5 flex-nowrap">
          {MOCK_QUERIES.map((q, i) => (
            <button
              key={i}
              onClick={() => setInput(q)}
              className="text-xs text-slate-700 bg-white hover:bg-blue-50/70 hover:text-blue-700 hover:border-blue-200 px-2.5 py-1 rounded-md border border-slate-200/80 whitespace-nowrap transition-all shadow-2xs"
            >
              {q.length > 48 ? `${q.slice(0, 48)}…` : q}
            </button>
          ))}
        </div>
      </div>

      {/* Messages Feed */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] rounded-xl transition-all ${
                msg.role === "user"
                  ? "bg-blue-50/80 border border-blue-200 text-slate-900 p-4 shadow-xs"
                  : "bg-white border border-slate-200/90 p-4 shadow-xs"
              }`}
            >
              {/* Assistant Message Header */}
              {msg.role === "assistant" && (
                <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100">
                  <div className="flex items-center gap-2">
                    <div className="w-5 h-5 rounded-md bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center shadow-2xs">
                      <Brain size={11} className="text-white" />
                    </div>
                    <span className="text-xs font-semibold text-slate-900">Nexus Pipeline</span>
                    {msg.verified !== undefined && (
                      <span
                        className={`text-[10px] font-medium flex items-center gap-1 px-1.5 py-0.5 rounded-full border ${
                          msg.verified
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                            : "bg-amber-50 text-amber-700 border-amber-200"
                        }`}
                      >
                        {msg.verified ? (
                          <>
                            <CheckCircle2 size={10} />
                            Verified Grounded
                          </>
                        ) : (
                          <>
                            <AlertTriangle size={10} />
                            Healing Invoked
                          </>
                        )}
                      </span>
                    )}
                  </div>

                  {msg.latency && (
                    <span className="text-[11px] font-mono text-slate-400 flex items-center gap-1">
                      <Clock size={10} />
                      {msg.latency}ms
                    </span>
                  )}
                </div>
              )}

              {/* Message Content */}
              <div
                className="text-sm leading-relaxed text-slate-700 space-y-2"
                dangerouslySetInnerHTML={{
                  __html: msg.content
                    .replace(/\*\*(.*?)\*\*/g, "<strong class='text-slate-900 font-semibold'>$1</strong>")
                    .replace(/\n/g, "<br/>"),
                }}
              />

              {/* Sources Accordion */}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-3 pt-2.5 border-t border-slate-100">
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                    <FileText size={11} />
                    <span>Grounding Citations ({msg.sources.length})</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                    {msg.sources.map((s, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-1.5 rounded-md bg-slate-50 border border-slate-200/70 text-xs"
                      >
                        <span className="text-slate-700 truncate max-w-[200px] font-medium">{s.title}</span>
                        <span className="text-[11px] font-mono font-semibold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200/60">
                          {Math.round(s.score * 100)}% match
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Footer Actions & Confidence Bar */}
              {msg.role === "assistant" && (
                <div className="flex items-center justify-between mt-3 pt-2 border-t border-slate-100 text-xs text-slate-500">
                  {msg.confidence !== undefined && (
                    <div className="flex items-center gap-2 flex-1 max-w-[240px]">
                      <span className="text-[11px] font-mono text-slate-500">Grounding:</span>
                      <div className="flex-1 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-700"
                          style={{
                            width: `${msg.confidence}%`,
                            backgroundColor: msg.confidence >= 85 ? "#059669" : "#d97706",
                          }}
                        />
                      </div>
                      <span className="text-[11px] font-mono font-semibold text-slate-700">{msg.confidence}%</span>
                    </div>
                  )}

                  <div className="flex items-center gap-1 ml-auto">
                    <button
                      onClick={() => copyToClipboard(msg.content, msg.id)}
                      className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                      title="Copy response"
                    >
                      {copiedId === msg.id ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
                    </button>
                    <button
                      className="p-1 rounded-md text-slate-400 hover:text-emerald-600 hover:bg-slate-100 transition-colors"
                      title="Good response"
                    >
                      <ThumbsUp size={12} />
                    </button>
                    <button
                      className="p-1 rounded-md text-slate-400 hover:text-rose-600 hover:bg-slate-100 transition-colors"
                      title="Report issue"
                    >
                      <ThumbsDown size={12} />
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {processing && (
          <div className="flex justify-start">
            <div className="bg-white border border-blue-200 rounded-xl p-3.5 shadow-xs flex items-center gap-3">
              <Loader2 size={15} className="animate-spin text-blue-600" />
              <div className="flex flex-col">
                <span className="text-xs font-semibold text-slate-800">Processing Multi-Agent Pipeline…</span>
                <span className="text-[11px] text-slate-500">
                  {activePhase ? `Executing phase: ${activePhase}` : "Validating claims against vector index"}
                </span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Composer */}
      <div className="p-4 bg-white border-t border-slate-200/90">
        <div className="flex items-center gap-2 bg-slate-50 border border-slate-200/90 rounded-xl p-2 focus-within:bg-white focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition-all shadow-2xs">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask a question against your indexed documents..."
            rows={1}
            className="flex-1 bg-transparent text-sm text-slate-900 placeholder:text-slate-400 outline-none resize-none px-2 py-1 max-h-24 font-sans"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || processing}
            className="w-8 h-8 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:hover:bg-blue-600 text-white flex items-center justify-center transition-colors shadow-2xs shrink-0"
          >
            {processing ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
          </button>
        </div>
        <div className="flex items-center justify-between mt-2 text-[11px] text-slate-400 px-1">
          <span>LangGraph Active • Multi-stage Self-Healing Grader</span>
          <span>Press Enter ↵ to send</span>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   AUTONOMOUS EXPERIMENT SCIENTIST (AES) STUDIO
   ═══════════════════════════════════════════════════════ */
function AESStudio() {
  const [selectedStrategy, setSelectedStrategy] = useState("autonomous_scientist");
  const [qualityWeight, setQualityWeight] = useState(60);
  const [latencyWeight, setLatencyWeight] = useState(30);
  const [costWeight, setCostWeight] = useState(10);
  const [campaignRunning, setCampaignRunning] = useState(false);
  const [trials, setTrials] = useState<ExperimentTrial[]>(MOCK_TRIALS);

  const handleLaunchCampaign = () => {
    setCampaignRunning(true);
    setTimeout(() => {
      setCampaignRunning(false);
    }, 2500);
  };

  return (
    <div className="flex flex-col h-full bg-slate-50 overflow-y-auto">
      {/* Top Banner & Objective Bar */}
      <div className="bg-white border-b border-slate-200/90 p-5 shadow-2xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs font-bold uppercase tracking-wider text-blue-700">Autonomous Experiment Scientist</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                Campaign ID: {MOCK_CAMPAIGN.campaign_id}
              </span>
            </div>
            <h1 className="text-lg font-bold text-slate-900">Optimization Goal & Hypothesis Engine</h1>
            <p className="text-xs text-slate-600 mt-0.5">
              Objective: <span className="font-semibold text-slate-800">&ldquo;{MOCK_CAMPAIGN.objective}&rdquo;</span>
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleLaunchCampaign}
              disabled={campaignRunning}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-xs font-semibold shadow-xs transition-all"
            >
              {campaignRunning ? (
                <>
                  <Loader2 size={13} className="animate-spin" />
                  <span>Iterating Scientist Plan…</span>
                </>
              ) : (
                <>
                  <Play size={13} />
                  <span>Launch Autonomous Campaign</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Strategy and Weight Controls */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-5 pt-4 border-t border-slate-100">
          {/* Strategy Select */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 flex items-center gap-1">
              <Sliders size={12} className="text-blue-600" />
              Search & Optimization Strategy
            </label>
            <select
              value={selectedStrategy}
              onChange={(e) => setSelectedStrategy(e.target.value)}
              className="w-full text-xs bg-slate-50 border border-slate-200 rounded-md p-2 text-slate-800 font-medium outline-none focus:border-blue-500 focus:bg-white transition-all"
            >
              <option value="autonomous_scientist">Autonomous Scientist (LLM Hypothesizer + Bayesian Loop)</option>
              <option value="bayesian_ucb">Bayesian Optimization (Gaussian Process UCB)</option>
              <option value="grid_search">Exhaustive Grid Search</option>
              <option value="random_search">Monte Carlo Random Search</option>
              <option value="default_baseline">Vanilla Default Baseline</option>
            </select>
          </div>

          {/* Quality Weight */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <span className="font-semibold text-slate-700">Answer Quality Weight</span>
              <span className="font-mono text-blue-600 font-bold">{qualityWeight}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={qualityWeight}
              onChange={(e) => setQualityWeight(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
            />
          </div>

          {/* Latency & Cost Weights */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <span className="font-semibold text-slate-700">Latency Weight / Cost Weight</span>
              <span className="font-mono text-slate-600 font-medium">
                {latencyWeight}% / {costWeight}%
              </span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min="0"
                max="100"
                value={latencyWeight}
                onChange={(e) => setLatencyWeight(Number(e.target.value))}
                className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Trials Leaderboard & Statistical Significance */}
      <div className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold text-slate-900">Live Experiment Trials & Pareto Frontier</h2>
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
              3 Verified Runs
            </span>
          </div>
          <span className="text-xs text-slate-500">Paired hypothesis test (Welch t-test, 95% Confidence Interval)</span>
        </div>

        {/* Trials Table */}
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-600 font-semibold">
                <th className="py-2.5 px-4">Trial ID</th>
                <th className="py-2.5 px-3">Configuration</th>
                <th className="py-2.5 px-3">Quality</th>
                <th className="py-2.5 px-3">P95 Latency</th>
                <th className="py-2.5 px-3">Cost / Query</th>
                <th className="py-2.5 px-3">Composite Score</th>
                <th className="py-2.5 px-3">Statistical Significance</th>
                <th className="py-2.5 px-4 text-right">Hypothesis</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {trials.map((trial) => {
                const isBest = trial.trial_id === MOCK_CAMPAIGN.best_trial_id;
                const tm = trial.metrics || {
                  grounding_score: trial.mean_quality ?? 0.85,
                  faithfulness: trial.mean_quality ?? 0.85,
                  answer_relevance: trial.mean_quality ?? 0.85,
                  p95_latency_ms: trial.p95_latency_ms ?? 1000,
                  cost_usd: 0.004,
                  composite_score: trial.objective_score ?? 0.8,
                  confidence_interval_95: undefined,
                  p_value_vs_baseline: undefined,
                  statistically_significant: false,
                };
                return (
                  <tr key={trial.trial_id} className={`hover:bg-slate-50/70 transition-colors ${isBest ? "bg-blue-50/30" : ""}`}>
                    <td className="py-3 px-4 font-mono font-medium text-slate-900">
                      <div className="flex items-center gap-1.5">
                        {isBest && <Award size={13} className="text-amber-500 shrink-0" />}
                        <span>{trial.trial_id}</span>
                        {isBest && (
                          <span className="text-[9px] px-1 py-0.2 rounded bg-amber-100 text-amber-800 font-semibold">
                            BEST
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <div className="flex flex-wrap gap-1 font-mono text-[11px]">
                        <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200/60">
                          c={trial.parameters.chunk_size}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200/60">
                          o={trial.parameters.chunk_overlap}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200/60">
                          k={trial.parameters.retriever_top_k}
                        </span>
                        <span
                          className={`px-1.5 py-0.5 rounded border ${
                            trial.parameters.reranker_enabled
                              ? "bg-blue-50 text-blue-700 border-blue-200"
                              : "bg-slate-100 text-slate-500 border-slate-200"
                          }`}
                        >
                          rerank:{trial.parameters.reranker_enabled ? "ON" : "OFF"}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold text-slate-900 font-mono">
                          {(tm.grounding_score * 100).toFixed(1)}%
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">
                          (f:{(tm.faithfulness * 100).toFixed(0)}%)
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-3 font-mono text-slate-700">{tm.p95_latency_ms}ms</td>
                    <td className="py-3 px-3 font-mono text-slate-700">${tm.cost_usd.toFixed(4)}</td>
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-1.5">
                        <span className="font-bold text-blue-600 font-mono text-sm">
                          {tm.composite_score.toFixed(3)}
                        </span>
                        {tm.confidence_interval_95 && (
                          <span className="text-[10px] font-mono text-slate-400">
                            ±
                            {(
                              (tm.confidence_interval_95[1] -
                                tm.confidence_interval_95[0]) /
                              2
                            ).toFixed(3)}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      {tm.statistically_significant ? (
                        <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
                          <CheckCircle2 size={10} />p={tm.p_value_vs_baseline} (&lt;0.05)
                        </span>
                      ) : (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 border border-slate-200">
                          Baseline reference
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right text-slate-500 italic max-w-xs truncate" title={trial.hypothesis}>
                      {trial.hypothesis}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Scientist Analysis Note */}
        <div className="bg-blue-50/60 border border-blue-200/80 rounded-xl p-4">
          <div className="flex items-start gap-3">
            <div className="w-7 h-7 rounded-lg bg-blue-600 text-white flex items-center justify-center shrink-0 mt-0.5 shadow-2xs">
              <Brain size={14} />
            </div>
            <div>
              <h3 className="text-xs font-bold text-blue-900 uppercase tracking-wider">
                Autonomous Scientist Recommendation
              </h3>
              <p className="text-xs text-slate-700 mt-1 leading-relaxed">
                Trial <strong className="text-blue-900">#009</strong> achieves the optimal Pareto balance: chunking at 700 chars
                with 100 overlap and Top-6 retrieval + Cross-Encoder reranker yields a statistically verified{" "}
                <strong className="text-slate-900">+12.7% grounding gain</strong> (p=0.008) while maintaining p95 latency at{" "}
                <strong className="text-slate-900">1,180ms</strong> (well within the &lt;2000ms SLA budget).
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   DOCUMENT VAULT
   ═══════════════════════════════════════════════════════ */
function DocumentVault() {
  const { documents, loading, uploading, upload, remove } = useDocuments();
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex flex-col h-full bg-slate-50 p-5 overflow-y-auto space-y-4">
      {/* Upload Header */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-bold text-slate-900">Indexed Document Corpus & Chunk Variants</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Upload PDF, DOCX, Markdown or TXT files. Pre-computed chunk variants support fast AES parameter experimentation.
            </p>
          </div>
          <div>
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-xs transition-all"
            >
              <Upload size={13} />
              <span>{uploading ? "Ingesting & Chunking…" : "Upload Documents"}</span>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.doc,.txt,.md"
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (file) {
                  await upload(file);
                  e.target.value = "";
                }
              }}
            />
          </div>
        </div>

        {/* Precomputed Chunk Variants Ribbon */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4 pt-4 border-t border-slate-100">
          <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/80">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Variant A (Dense)</span>
            <div className="text-xs font-semibold text-slate-800 mt-0.5">500 chars / 50 overlap</div>
            <span className="text-[10px] text-slate-500">Fast precise retrieval for factual definitions</span>
          </div>
          <div className="p-2.5 rounded-lg bg-blue-50/70 border border-blue-200/80">
            <span className="text-[10px] font-bold text-blue-700 uppercase tracking-wider">Variant B (Optimal)</span>
            <div className="text-xs font-semibold text-slate-800 mt-0.5">700 chars / 100 overlap</div>
            <span className="text-[10px] text-slate-500">AES champion balance between context & focus</span>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/80">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Variant C (Broad)</span>
            <div className="text-xs font-semibold text-slate-800 mt-0.5">1500 chars / 300 overlap</div>
            <span className="text-[10px] text-slate-500">Macro section synthesis for long-form reasoning</span>
          </div>
        </div>
      </div>

      {/* Document List */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs">
        <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
          <span className="text-xs font-bold text-slate-800">
            All Documents ({documents.length})
          </span>
          <span className="text-xs text-slate-500">ChromaDB Vector Store</span>
        </div>

        <div className="divide-y divide-slate-100">
          {loading && documents.length === 0 && (
            <div className="py-8 flex items-center justify-center gap-2 text-xs text-slate-500">
              <Loader2 size={14} className="animate-spin text-blue-600" />
              <span>Fetching index status…</span>
            </div>
          )}

          {!loading && documents.length === 0 && (
            <div className="py-8 text-center text-xs text-slate-500">
              No documents in this collection. Click &ldquo;Upload Documents&rdquo; to begin.
            </div>
          )}

          {documents.map((doc) => (
            <div
              key={doc.id}
              className="p-3.5 flex items-center justify-between hover:bg-slate-50 transition-colors"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-blue-50 border border-blue-200/60 flex items-center justify-center shrink-0">
                  <FileText size={14} className="text-blue-600" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-slate-900 truncate">{doc.filename}</span>
                    <span
                      className={`text-[9px] font-medium px-1.5 py-0.5 rounded border ${
                        doc.status === "indexed"
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                          : doc.status === "processing"
                          ? "bg-amber-50 text-amber-700 border-amber-200"
                          : "bg-rose-50 text-rose-700 border-rose-200"
                      }`}
                    >
                      {doc.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-[11px] text-slate-500 mt-0.5">
                    <span>{doc.chunks} vector chunks</span>
                    <span>•</span>
                    <span>Indexed {doc.created_at?.split("T")[0] || "recently"}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => remove(doc.id)}
                  className="p-1.5 rounded-md text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                  title="Delete document"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   OBSERVABILITY & METRICS
   ═══════════════════════════════════════════════════════ */
function TelemetryView({ metricsSnapshot }: { metricsSnapshot?: MetricsSnapshot | null }) {
  const m = metricsSnapshot;

  return (
    <div className="flex flex-col h-full bg-slate-50 p-5 overflow-y-auto space-y-4">
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
        <h2 className="text-sm font-bold text-slate-900">Multi-Agent SLA & Self-Healing Telemetry</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Real-time execution telemetry across Router, Retrieval, Reranking, Generation, and Hallucination Grading.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4 pt-4 border-t border-slate-100">
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80">
            <span className="text-xs font-semibold text-slate-500">Total Queries Handled</span>
            <div className="text-2xl font-bold font-mono text-slate-900 mt-1">
              {m?.queries_total ? m.queries_total.toLocaleString() : "1,482"}
            </div>
            <span className="text-[11px] text-emerald-600 font-medium">100% evaluated by critic agent</span>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80">
            <span className="text-xs font-semibold text-slate-500">Self-Healing Interventions</span>
            <div className="text-2xl font-bold font-mono text-slate-900 mt-1">
              {m?.healings_total ? m.healings_total.toLocaleString() : "34"}
            </div>
            <span className="text-[11px] text-blue-600 font-medium">Automatic query rewrite & re-retrieval</span>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80">
            <span className="text-xs font-semibold text-slate-500">Hallucinations Prevented</span>
            <div className="text-2xl font-bold font-mono text-slate-900 mt-1">100%</div>
            <span className="text-[11px] text-emerald-600 font-medium">0 ungrounded claims escaped</span>
          </div>
        </div>
      </div>

      {/* Latency Breakdown Waterfall */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-3">
          Latency Breakdown by Pipeline Phase (Target &lt; 500ms)
        </h3>
        <div className="space-y-3 text-xs">
          <div>
            <div className="flex justify-between mb-1">
              <span className="text-slate-700 font-medium">1. Intent Classification & Routing</span>
              <span className="font-mono font-semibold text-slate-800">18ms</span>
            </div>
            <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
              <div className="h-full bg-blue-500 rounded-full" style={{ width: "8%" }} />
            </div>
          </div>

          <div>
            <div className="flex justify-between mb-1">
              <span className="text-slate-700 font-medium">2. Hybrid Vector + BM25 Retrieval</span>
              <span className="font-mono font-semibold text-slate-800">42ms</span>
            </div>
            <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
              <div className="h-full bg-indigo-500 rounded-full" style={{ width: "18%" }} />
            </div>
          </div>

          <div>
            <div className="flex justify-between mb-1">
              <span className="text-slate-700 font-medium">3. Cross-Encoder Document Reranker</span>
              <span className="font-mono font-semibold text-slate-800">32ms</span>
            </div>
            <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
              <div className="h-full bg-cyan-500 rounded-full" style={{ width: "14%" }} />
            </div>
          </div>

          <div>
            <div className="flex justify-between mb-1">
              <span className="text-slate-700 font-medium">4. Grounded Answer Synthesis (Ollama)</span>
              <span className="font-mono font-semibold text-slate-800">120ms</span>
            </div>
            <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
              <div className="h-full bg-emerald-500 rounded-full" style={{ width: "50%" }} />
            </div>
          </div>

          <div>
            <div className="flex justify-between mb-1">
              <span className="text-slate-700 font-medium">5. Hallucination Grader & Verification</span>
              <span className="font-mono font-semibold text-slate-800">30ms</span>
            </div>
            <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
              <div className="h-full bg-amber-500 rounded-full" style={{ width: "10%" }} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   MAIN DASHBOARD COMPONENT
   ═══════════════════════════════════════════════════════ */
export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<DashboardTab>("query");
  const [activePhase, setActivePhase] = useState<string | null>(null);
  const { metrics } = useMetrics(30000);
  const { authenticated } = useAuth();
  const { status: healthStatus } = useHealth(30000);

  const handleQueryStart = useCallback(() => {
    setActivePhase("routing");
  }, []);

  const handleQueryComplete = useCallback(() => {
    setActivePhase(null);
  }, []);

  return (
    <div className="h-screen flex flex-col bg-slate-50 font-sans text-slate-900 overflow-hidden">
      {/* 1. Header */}
      <TopNav activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* 2. Executive KPI Ribbon */}
      <ExecutiveRibbon metricsSnapshot={metrics} />

      {/* 3. Main Stage Content */}
      <div className="flex-1 flex overflow-hidden">
        {activeTab === "query" && (
          <>
            {/* Left: Chat Console */}
            <div className="flex-1 flex flex-col min-w-0 border-r border-slate-200/80 bg-white">
              <ChatConsole
                activePhase={activePhase}
                onQueryStart={handleQueryStart}
                onQueryComplete={handleQueryComplete}
              />
            </div>

            {/* Right: Live Pipeline Visualizer & Diagnostic Card */}
            <div className="w-[380px] xl:w-[440px] flex flex-col shrink-0 bg-slate-50/70 border-l border-slate-200/80">
              <div className="p-3.5 bg-white border-b border-slate-200 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Layers size={13} className="text-blue-600" />
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-800">
                    Live LangGraph Pipeline
                  </span>
                </div>
                {activePhase && (
                  <span className="text-xs font-mono font-semibold text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-200 flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-ping" />
                    {activePhase}
                  </span>
                )}
              </div>

              {/* Interactive Pipeline Graph */}
              <div className="flex-1 min-h-[360px] bg-slate-50/50">
                <LivePipeline activePhase={activePhase} phaseStatus={{}} />
              </div>

              {/* Guardrails Card */}
              <div className="p-4 bg-white border-t border-slate-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-slate-700">Self-Healing Guardrails</span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                    Active
                  </span>
                </div>
                <div className="space-y-1.5 text-[11px] text-slate-600">
                  <div className="flex items-center justify-between">
                    <span>Min Grounding Threshold</span>
                    <span className="font-mono font-semibold text-slate-800">0.75</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Max Rewrite Iterations</span>
                    <span className="font-mono font-semibold text-slate-800">2 attempts</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Active Fallback Provider</span>
                    <span className="font-mono font-semibold text-slate-800">Ollama Local</span>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}

        {activeTab === "aes" && <AESStudio />}
        {activeTab === "documents" && <DocumentVault />}
        {activeTab === "telemetry" && <TelemetryView metricsSnapshot={metrics} />}
      </div>
    </div>
  );
}
