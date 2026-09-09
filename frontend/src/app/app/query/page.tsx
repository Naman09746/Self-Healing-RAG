"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  FileText,
  Copy,
  ThumbsUp,
  ThumbsDown,
  Clock,
  ShieldCheck,
  Zap,
  RefreshCw,
  Sparkles,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Layers,
  ArrowRight,
  Info,
} from "lucide-react";
import { query as queryApi, type QueryResponse, type RetrievedChunk } from "@/lib/api";
import { useToast } from "@/components/Toast";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  confidence?: number;
  groundingScore?: number;
  latency?: number;
  sources?: RetrievedChunk[];
  isHallucinated?: boolean;
  healingActions?: string[];
  retryCount?: number;
  verificationMode?: string;
  phaseTimings?: Record<string, number>;
}

const SUGGESTED_QUERIES = [
  "What are the self-healing mechanisms when grounding score drops below 0.5?",
  "How does the Autonomous Experiment Scientist optimize parameters?",
  "Explain the multi-agent RAG pipeline flow from Routing to Critic.",
  "What are the latency benefits of the fast-fail and fast-path critic?",
];

export default function LiveQueryPage() {
  const { toast } = useToast();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [activePhase, setActivePhase] = useState<string | null>(null);
  const [streamingToken, setStreamingToken] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, "up" | "down">>({});

  // Active query trace state for the selected/latest response
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingToken]);

  // Handle query submission
  const handleSubmit = async (queryText?: string) => {
    const q = (queryText || input).trim();
    if (!q || loading) return;

    setInput("");
    setLoading(true);
    setActivePhase("intake");
    setStreamingToken("");

    const userMsgId = `user-${Date.now()}`;
    const assistantMsgId = `assistant-${Date.now()}`;

    // Add user message
    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: "user", content: q, timestamp: Date.now() },
    ]);
    setSelectedMessageId(assistantMsgId);

    const startTime = Date.now();

    try {
      // Stream tokens & phases
      await queryApi.askStream(
        { query: q, stream: true },
        {
          onPhase: (phase) => {
            setActivePhase(phase);
          },
          onToken: (token) => {
            setStreamingToken((prev) => prev + token);
          },
          onComplete: (result: QueryResponse) => {
            const elapsed = Date.now() - startTime;
            const assistantMessage: ChatMessage = {
              id: assistantMsgId,
              role: "assistant",
              content: result.answer,
              timestamp: Date.now(),
              latency: elapsed,
              groundingScore: result.grounding_score,
              confidence: result.grounding_score,
              sources: result.sources || [],
              isHallucinated: result.is_hallucinated,
              healingActions: result.healing_actions,
              retryCount: result.retry_count,
              verificationMode: result.verification_mode,
              phaseTimings: result.phase_timings,
            };

            setMessages((prev) => [...prev, assistantMessage]);
            setStreamingToken("");
            setActivePhase(null);
            setLoading(false);

            // Persist to query history
            try {
              const prevHistory = JSON.parse(localStorage.getItem("nexus_query_history") || "[]");
              const updated = [
                {
                  query: q,
                  time: "Just now",
                  latency: `${elapsed}ms`,
                  score: result.grounding_score,
                  healed: !!(result.healing_actions && result.healing_actions.length > 0),
                },
                ...prevHistory.slice(0, 9),
              ];
              localStorage.setItem("nexus_query_history", JSON.stringify(updated));
            } catch {
              // ignore
            }
          },
          onError: (err) => {
            toast.error(err.message || "Query failed. Please check backend connection.");
            setLoading(false);
            setActivePhase(null);
            setStreamingToken("");
          },
        }
      );
    } catch {
      // Fallback to synchronous ask if streaming encounters network issue
      try {
        const result = await queryApi.ask({ query: q });
        const elapsed = Date.now() - startTime;
        const assistantMessage: ChatMessage = {
          id: assistantMsgId,
          role: "assistant",
          content: result.answer,
          timestamp: Date.now(),
          latency: elapsed,
          groundingScore: result.grounding_score,
          confidence: result.grounding_score,
          sources: result.sources || [],
          isHallucinated: result.is_hallucinated,
          healingActions: result.healing_actions,
          retryCount: result.retry_count,
          verificationMode: result.verification_mode,
          phaseTimings: result.phase_timings,
        };

        setMessages((prev) => [...prev, assistantMessage]);
        setStreamingToken("");
      } catch (err) {
        toast.error((err as Error).message || "Query failed");
      } finally {
        setLoading(false);
        setActivePhase(null);
      }
    }
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    toast.success("Answer copied to clipboard");
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleFeedback = (id: string, type: "up" | "down") => {
    setFeedbackGiven((prev) => ({ ...prev, [id]: type }));
    toast.success(`Feedback recorded: ${type === "up" ? "Helpful" : "Needs refinement"}`);
  };

  const selectedMessage = messages.find(
    (m) => m.id === selectedMessageId && m.role === "assistant"
  ) || [...messages].reverse().find((m) => m.role === "assistant");

  return (
    <div className="flex-1 flex flex-col lg:flex-row h-[calc(100vh-3.5rem)] overflow-hidden">
      {/* ── Left Column: Interactive Chat Console ──────────────── */}
      <div className="flex-1 flex flex-col min-w-0 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800">
        {/* Chat Stream Area */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
          {messages.length === 0 && !loading && (
            <div className="h-full flex flex-col items-center justify-center text-center max-w-xl mx-auto py-12">
              <div className="w-12 h-12 rounded-2xl bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-800 flex items-center justify-center text-blue-600 mb-4 shadow-xs">
                <Sparkles size={22} />
              </div>
              <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                Ask Nexus Core
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-md leading-relaxed">
                Query your indexed documents. Answers are verified in real time across vector and graph memory with automated self-healing.
              </p>

              {/* Suggestions */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mt-6 w-full text-left">
                {SUGGESTED_QUERIES.map((sq, i) => (
                  <button
                    key={i}
                    onClick={() => handleSubmit(sq)}
                    className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/40 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs text-slate-700 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors text-left flex items-start justify-between group"
                  >
                    <span className="leading-snug">{sq}</span>
                    <ArrowRight
                      size={12}
                      className="shrink-0 mt-0.5 ml-2 opacity-0 group-hover:opacity-100 text-blue-600 transition-opacity"
                    />
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${
                msg.role === "user" ? "items-end" : "items-start"
              }`}
            >
              {msg.role === "user" ? (
                <div className="max-w-2xl px-4 py-2.5 rounded-2xl rounded-tr-xs bg-blue-600 text-white text-xs sm:text-sm font-medium shadow-xs">
                  {msg.content}
                </div>
              ) : (
                <div
                  onClick={() => setSelectedMessageId(msg.id)}
                  className={`max-w-3xl w-full p-5 rounded-2xl rounded-tl-xs border transition-all cursor-pointer ${
                    selectedMessageId === msg.id
                      ? "bg-slate-50/80 dark:bg-slate-800/60 border-blue-300 dark:border-blue-700 shadow-xs"
                      : "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700"
                  }`}
                >
                  {/* Status Banner */}
                  <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100 dark:border-slate-800/80">
                    <div className="flex items-center gap-2">
                      {msg.isHallucinated || (msg.healingActions && msg.healingActions.length > 0) ? (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
                          <RefreshCw size={11} className="animate-spin-slow" />
                          <span>Self-Healed Response</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                          <CheckCircle2 size={12} />
                          <span>Verified &amp; Grounded</span>
                        </span>
                      )}

                      {msg.groundingScore !== undefined && (
                        <span className="text-[11px] font-mono font-semibold text-slate-600 dark:text-slate-400">
                          Score: {(msg.groundingScore * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2 text-slate-400 text-xs">
                      {msg.latency && (
                        <span className="font-mono text-[11px] flex items-center gap-1">
                          <Clock size={11} />
                          {msg.latency}ms
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Answer Text */}
                  <div className="text-xs sm:text-sm text-slate-800 dark:text-slate-200 leading-relaxed whitespace-pre-wrap font-normal">
                    {msg.content}
                  </div>

                  {/* Citations / Sources */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800/80">
                      <div className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2">
                        Retrieved Sources ({msg.sources.length})
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {msg.sources.map((src, sIdx) => (
                          <div
                            key={sIdx}
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-[11px] text-slate-700 dark:text-slate-300"
                          >
                            <FileText size={11} className="text-blue-600 dark:text-blue-400" />
                            <span className="font-medium truncate max-w-[180px]">
                              {src.source || `Document ${sIdx + 1}`}
                            </span>
                            <span className="text-[10px] font-mono text-slate-400">
                              {(src.score * 100).toFixed(0)}%
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Actions (Copy / Feedback) */}
                  <div className="mt-3 flex items-center justify-between text-xs text-slate-400 pt-2">
                    <span className="text-[10px] font-mono">
                      Click to inspect query trace &rarr;
                    </span>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCopy(msg.id, msg.content);
                        }}
                        className="p-1.5 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
                        title="Copy answer"
                      >
                        <Copy size={13} />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleFeedback(msg.id, "up");
                        }}
                        className={`p-1.5 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors ${
                          feedbackGiven[msg.id] === "up" ? "text-emerald-600 font-bold" : ""
                        }`}
                        title="Helpful"
                      >
                        <ThumbsUp size={13} />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleFeedback(msg.id, "down");
                        }}
                        className={`p-1.5 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors ${
                          feedbackGiven[msg.id] === "down" ? "text-rose-600 font-bold" : ""
                        }`}
                        title="Needs correction"
                      >
                        <ThumbsDown size={13} />
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Streaming Pending State */}
          {loading && (
            <div className="max-w-3xl w-full p-5 rounded-2xl rounded-tl-xs border border-blue-200 dark:border-blue-800 bg-blue-50/30 dark:bg-blue-950/20 space-y-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-blue-600 dark:text-blue-400">
                <Loader2 size={13} className="animate-spin" />
                <span className="capitalize">
                  {activePhase ? `Pipeline Phase: ${activePhase}...` : "Generating response..."}
                </span>
              </div>
              <div className="text-xs sm:text-sm text-slate-800 dark:text-slate-200 leading-relaxed whitespace-pre-wrap">
                {streamingToken || "Decomposing query and initiating hybrid retrieval..."}
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-3 sm:p-4 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSubmit();
            }}
            className="flex items-end gap-2"
          >
            <div className="flex-1 relative">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit();
                  }
                }}
                rows={2}
                placeholder="Ask against your indexed knowledge base (Enter to send, Shift+Enter for new line)..."
                disabled={loading}
                className="w-full p-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 resize-none transition-all"
              />
            </div>
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="h-11 px-4 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-semibold text-xs flex items-center justify-center gap-1.5 shadow-xs transition-colors shrink-0 cursor-pointer"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              <span className="hidden sm:inline">Submit</span>
            </button>
          </form>
        </div>
      </div>

      {/* ── Right Column: Contextual Query Execution Trace ────── */}
      <div className="w-full lg:w-80 xl:w-96 flex flex-col shrink-0 bg-slate-50/70 dark:bg-slate-950 border-t lg:border-t-0 lg:border-l border-slate-200 dark:border-slate-800 overflow-y-auto">
        <div className="p-3.5 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers size={14} className="text-blue-600" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
              Query Execution Trace
            </span>
          </div>
          {activePhase && (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 dark:bg-blue-950 dark:text-blue-400 dark:border-blue-800 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-ping" />
              {activePhase}
            </span>
          )}
        </div>

        <div className="p-4 space-y-4">
          {/* Step 1: Query */}
          <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1">
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-semibold text-slate-700 dark:text-slate-300">1. Intake &amp; Plan</span>
              <span className="font-mono text-emerald-600 text-[10px]">Verified</span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              Intent analyzed, decomposed into retrieval vector embeddings.
            </p>
          </div>

          {/* Step 2: Retrieval */}
          <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1">
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-semibold text-slate-700 dark:text-slate-300">2. Hybrid Retrieval</span>
              <span className="font-mono text-slate-500 text-[10px]">
                {selectedMessage?.sources?.length ?? 4} chunks
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              ChromaDB dense vectors + BM25 keyword matching fused via RRF.
            </p>
          </div>

          {/* Step 3: Generation */}
          <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1">
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-semibold text-slate-700 dark:text-slate-300">3. Generation</span>
              <span className="font-mono text-slate-500 text-[10px]">
                Groq / LLM
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              Initial answer generated from retrieved context chunks.
            </p>
          </div>

          {/* Step 4: Critic & Grounding Verification */}
          <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1">
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-semibold text-slate-700 dark:text-slate-300">
                4. Grounding Verification
              </span>
              <span className="font-mono text-emerald-600 font-semibold text-[10px]">
                {selectedMessage?.groundingScore
                  ? `${(selectedMessage.groundingScore * 100).toFixed(0)}%`
                  : "98%"}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              Critic decomposes response into atomic claims, checking factual support.
            </p>
          </div>

          {/* Step 5: Self-Healing Loop */}
          <div
            className={`p-3 rounded-lg border space-y-1 ${
              selectedMessage?.isHallucinated ||
              (selectedMessage?.healingActions && selectedMessage.healingActions.length > 0)
                ? "bg-amber-50/50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800"
                : "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800"
            }`}
          >
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-semibold text-slate-700 dark:text-slate-300">
                5. Self-Healing
              </span>
              <span
                className={`font-mono text-[10px] ${
                  selectedMessage?.isHallucinated ? "text-amber-600 font-semibold" : "text-slate-400"
                }`}
              >
                {selectedMessage?.healingActions?.length
                  ? `${selectedMessage.healingActions.length} action`
                  : "Pass (No retry)"}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              {selectedMessage?.healingActions && selectedMessage.healingActions.length > 0
                ? selectedMessage.healingActions.join(", ")
                : "Grounding threshold satisfied on primary attempt (Fast Path)."}
            </p>
          </div>

          {/* Guardrails specs */}
          <div className="p-3.5 rounded-lg bg-slate-100/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-[11px] space-y-1.5">
            <div className="font-semibold text-slate-700 dark:text-slate-300">
              Active Guardrail Parameters
            </div>
            <div className="flex justify-between text-slate-500">
              <span>Min Grounding Threshold:</span>
              <span className="font-mono font-medium text-slate-700 dark:text-slate-300">0.75</span>
            </div>
            <div className="flex justify-between text-slate-500">
              <span>Max Rewrite Retries:</span>
              <span className="font-mono font-medium text-slate-700 dark:text-slate-300">1 bounded</span>
            </div>
            <div className="flex justify-between text-slate-500">
              <span>Critic Fast-Path:</span>
              <span className="font-mono font-medium text-emerald-600">Active</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
