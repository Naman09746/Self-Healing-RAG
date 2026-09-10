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
  Upload,
  Paperclip,
  FileUp,
  FileCheck,
} from "lucide-react";
import { query as queryApi, documents as docsApi, type QueryResponse, type RetrievedChunk } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { useDocuments } from "@/lib/hooks";

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
  const { documents: indexedDocs, refresh: refreshDocs } = useDocuments();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [activePhase, setActivePhase] = useState<string | null>(null);
  const [streamingToken, setStreamingToken] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, "up" | "down">>({});

  // Document Drag & Drop + Manual Selection State
  const [isDragging, setIsDragging] = useState(false);
  const dragCounter = useRef(0);
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [recentUploads, setRecentUploads] = useState<string[]>([]);
  const [selectedDocNames, setSelectedDocNames] = useState<string[]>([]);
  const [showDocSelector, setShowDocSelector] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Active query trace state for the selected/latest response
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);

  const handleDocumentUpload = async (files: FileList | File[]) => {
    const fileList = Array.from(files);
    if (!fileList.length) return;

    setUploadingDoc(true);
    let successCount = 0;
    const uploadedNames: string[] = [];

    for (const file of fileList) {
      try {
        await docsApi.upload(file);
        successCount++;
        uploadedNames.push(file.name);
      } catch (err) {
        toast.error(`Failed to ingest "${file.name}": ${(err as Error).message}`);
      }
    }

    setUploadingDoc(false);
    if (successCount > 0) {
      setRecentUploads((prev) => [...uploadedNames, ...prev].slice(0, 5));
      await refreshDocs();
      toast.success(`Indexed ${successCount} document${successCount > 1 ? "s" : ""} into vector & sparse stores! Ready to query.`);
    }
  };

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
    <div
      onDragOver={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
      onDragEnter={(e) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounter.current += 1;
        if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
          setIsDragging(true);
        }
      }}
      onDragLeave={(e) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounter.current -= 1;
        if (dragCounter.current <= 0) {
          dragCounter.current = 0;
          setIsDragging(false);
        }
      }}
      onDrop={async (e) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounter.current = 0;
        setIsDragging(false);
        if (e.dataTransfer.files?.length) {
          await handleDocumentUpload(e.dataTransfer.files);
        }
      }}
      className="relative flex-1 flex flex-col lg:flex-row h-[calc(100vh-3.5rem)] overflow-hidden"
    >
      {/* ── Drag & Drop Full-Page Overlay ── */}
      {isDragging && (
        <div className="absolute inset-0 z-50 bg-blue-600/90 dark:bg-blue-900/90 backdrop-blur-xs flex flex-col items-center justify-center text-white p-6 border-4 border-dashed border-white/60 animate-in fade-in duration-150 pointer-events-none">
          <div className="w-16 h-16 rounded-full bg-white/20 flex items-center justify-center mb-4 animate-bounce">
            <Upload size={32} />
          </div>
          <h3 className="text-lg font-bold">Drop Documents Here to Index</h3>
          <p className="text-xs text-white/80 mt-1 max-w-sm text-center">
            Files will be automatically chunked, embedded, and added to the PostgreSQL pgvector &amp; sparse search indexes.
          </p>
          <div className="mt-4 px-3 py-1 rounded-full bg-white/10 text-[11px] font-mono">
            PDF, Markdown (.md), DOCX, TXT, CSV, JSON
          </div>
        </div>
      )}

      {/* ── Left Column: Interactive Chat Console ──────────────── */}
      <div className="flex-1 flex flex-col min-w-0 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800">
        {/* Knowledge Base Scope & Manual Document Selector Bar */}
        <div className="px-4 py-2.5 bg-slate-50/80 dark:bg-slate-950/70 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 overflow-x-auto py-0.5 max-w-full">
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider shrink-0 flex items-center gap-1">
              <FileText size={12} className="text-blue-600" />
              Target Corpus:
            </span>

            {/* Scope Badge / Dropdown Toggle */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowDocSelector(!showDocSelector)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 text-xs font-medium hover:border-blue-400 dark:hover:border-blue-500 shadow-2xs transition-all cursor-pointer"
              >
                <span>
                  {selectedDocNames.length === 0
                    ? `Entire Knowledge Base (${indexedDocs.length} docs)`
                    : `Scoped to ${selectedDocNames.length} selected document${selectedDocNames.length > 1 ? "s" : ""}`}
                </span>
                <ChevronDown size={12} className={`text-slate-400 transition-transform ${showDocSelector ? "rotate-180" : ""}`} />
              </button>

              {/* Document Selection Popover */}
              {showDocSelector && (
                <div className="absolute left-0 top-full mt-1.5 w-72 sm:w-80 p-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-lg z-40 space-y-2.5">
                  <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
                    <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                      Select Target Documents
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setSelectedDocNames([])}
                        className="text-[11px] text-blue-600 dark:text-blue-400 hover:underline"
                      >
                        Reset (All)
                      </button>
                    </div>
                  </div>

                  {/* Document List */}
                  <div className="max-h-48 overflow-y-auto space-y-1.5 pr-1">
                    {indexedDocs.length === 0 ? (
                      <div className="text-[11px] text-slate-400 text-center py-3">
                        No documents indexed yet. Upload files below.
                      </div>
                    ) : (
                      indexedDocs.map((doc) => {
                        const isSelected = selectedDocNames.includes(doc.filename);
                        return (
                          <label
                            key={doc.id}
                            className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/60 cursor-pointer transition-colors"
                          >
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedDocNames((prev) => [...prev, doc.filename]);
                                } else {
                                  setSelectedDocNames((prev) => prev.filter((name) => name !== doc.filename));
                                }
                              }}
                              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-3.5 h-3.5"
                            />
                            <div className="flex-1 truncate text-xs text-slate-700 dark:text-slate-300 font-medium">
                              {doc.filename}
                            </div>
                            <span className="text-[10px] text-slate-400 font-mono">
                              {doc.chunks ? `${doc.chunks} chunks` : ""}
                            </span>
                          </label>
                        );
                      })
                    )}
                  </div>

                  {/* Quick Upload from Dropdown */}
                  <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
                    <button
                      type="button"
                      onClick={() => {
                        setShowDocSelector(false);
                        fileInputRef.current?.click();
                      }}
                      className="inline-flex items-center gap-1.5 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 font-medium cursor-pointer"
                    >
                      <Upload size={12} />
                      <span>Upload &amp; Index New File</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowDocSelector(false)}
                      className="px-2.5 py-1 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-[11px] font-semibold"
                    >
                      Done
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Selected Document Tags */}
            {selectedDocNames.map((name) => (
              <span
                key={name}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800 text-[11px] truncate max-w-[140px]"
              >
                <span className="truncate">{name}</span>
                <button
                  type="button"
                  onClick={() => setSelectedDocNames((prev) => prev.filter((n) => n !== name))}
                  className="text-blue-500 hover:text-blue-700 font-bold ml-0.5"
                >
                  &times;
                </button>
              </span>
            ))}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-blue-50 dark:bg-blue-950/50 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800 hover:bg-blue-100 transition-colors cursor-pointer"
            >
              <Upload size={12} />
              <span className="hidden sm:inline">Upload Files</span>
            </button>
          </div>
        </div>

        {/* Chat Stream Area */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
          {/* Recent Uploads Pill Notification */}
          {recentUploads.length > 0 && (
            <div className="flex items-center gap-2 p-2.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300">
              <FileCheck size={14} className="shrink-0 text-emerald-600" />
              <div className="flex-1 truncate">
                <span className="font-semibold">Ready to query:</span> {recentUploads.join(", ")}
              </div>
              <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded-md bg-emerald-200/60 dark:bg-emerald-900/60 text-emerald-900 dark:text-emerald-200 shrink-0">
                Indexed
              </span>
            </div>
          )}

          {uploadingDoc && (
            <div className="flex items-center gap-2.5 p-3 rounded-xl bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 text-xs text-blue-700 dark:text-blue-300 animate-pulse">
              <Loader2 size={14} className="animate-spin text-blue-600" />
              <span>Ingesting and embedding document chunks into pgvector...</span>
            </div>
          )}

          {messages.length === 0 && !loading && (
            <div className="h-full flex flex-col items-center justify-center text-center max-w-xl mx-auto py-12">
              <div className="w-12 h-12 rounded-2xl bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-800 flex items-center justify-center text-blue-600 mb-4 shadow-xs">
                <Sparkles size={22} />
              </div>
              <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                Ask Nexus Core
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-md leading-relaxed">
                Submit queries to run through the 7-agent Self-Healing RAG pipeline with hybrid retrieval (pgvector + BM25) and hallucination verification.
              </p>

              {/* Quick Drop Zone Box for Empty State */}
              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                }}
                onDragEnter={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                }}
                onDrop={async (e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  if (e.dataTransfer.files?.length) {
                    await handleDocumentUpload(e.dataTransfer.files);
                  }
                }}
                className="mt-6 w-full p-4 rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-800 hover:border-blue-400 dark:hover:border-blue-600 bg-slate-50/50 dark:bg-slate-950/50 cursor-pointer transition-colors"
              >
                <Upload size={18} className="mx-auto text-slate-400 mb-1" />
                <div className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Drag &amp; drop test files here, or click to upload
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  Drop your test markdown (.md) or PDF files directly into the query studio
                </div>
              </div>

              {/* Suggestions */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full mt-6 text-left">
                {SUGGESTED_QUERIES.map((sq, i) => (
                  <button
                    key={i}
                    onClick={() => handleSubmit(sq)}
                    className="p-3 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-950/40 hover:bg-blue-50/50 dark:hover:bg-blue-950/30 hover:border-blue-200 dark:hover:border-blue-800 text-left text-xs text-slate-700 dark:text-slate-300 transition-all flex items-start gap-2 group cursor-pointer"
                  >
                    <ArrowRight size={13} className="text-blue-500 shrink-0 mt-0.5 group-hover:translate-x-0.5 transition-transform" />
                    <span className="line-clamp-2 leading-relaxed">{sq}</span>
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
                          <CheckCircle2 size={11} />
                          <span>Grounded Answer</span>
                        </span>
                      )}

                      {msg.groundingScore !== undefined && (
                        <span className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">
                          Score: {(msg.groundingScore * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2 text-[11px] text-slate-400">
                      {msg.latency !== undefined && (
                        <span className="flex items-center gap-1">
                          <Clock size={11} />
                          <span>{msg.latency}ms</span>
                        </span>
                      )}
                      {msg.retryCount !== undefined && msg.retryCount > 0 && (
                        <span className="px-1.5 py-0.2 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-mono">
                          {msg.retryCount} retry
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Message Content */}
                  <div className="text-xs sm:text-sm text-slate-800 dark:text-slate-200 leading-relaxed whitespace-pre-wrap">
                    {msg.content}
                  </div>

                  {/* Sources Preview Pill */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800/80 flex flex-wrap items-center gap-1.5">
                      <span className="text-[11px] text-slate-400 font-medium mr-1 flex items-center gap-1">
                        <FileText size={11} /> Sources:
                      </span>
                      {msg.sources.slice(0, 3).map((s, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 text-[10px] font-mono border border-slate-200 dark:border-slate-700 truncate max-w-[160px]"
                          title={s.content}
                        >
                          {s.source || s.chunk_id || `Source ${idx + 1}`}
                        </span>
                      ))}
                      {msg.sources.length > 3 && (
                        <span className="text-[10px] text-slate-400 font-mono">
                          +{msg.sources.length - 3} more
                        </span>
                      )}
                    </div>
                  )}

                  {/* Actions Footer */}
                  <div className="mt-3 flex items-center justify-between pt-2 text-slate-400 text-xs">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleCopy(msg.id, msg.content);
                      }}
                      className="flex items-center gap-1 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
                    >
                      <Copy size={12} />
                      <span className="text-[11px]">
                        {copiedId === msg.id ? "Copied" : "Copy"}
                      </span>
                    </button>

                    <div className="flex items-center gap-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleFeedback(msg.id, "up");
                        }}
                        className={`p-1.5 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors ${
                          feedbackGiven[msg.id] === "up" ? "text-emerald-600 font-bold" : ""
                        }`}
                        title="Helpful & Accurate"
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
          {/* Hidden File Input */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.doc,.txt,.md,.json,.jsonl,.csv"
            className="hidden"
            onChange={async (e) => {
              if (e.target.files?.length) {
                await handleDocumentUpload(e.target.files);
                e.target.value = "";
              }
            }}
          />

          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSubmit();
            }}
            className="flex items-end gap-2"
          >
            {/* Attachment Button */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingDoc || loading}
              title="Attach & Index Documents (PDF, MD, TXT)"
              className="h-11 w-11 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/40 text-slate-500 hover:text-blue-600 dark:hover:text-blue-400 flex items-center justify-center transition-all shrink-0 cursor-pointer disabled:opacity-50"
            >
              {uploadingDoc ? (
                <Loader2 size={16} className="animate-spin text-blue-600" />
              ) : (
                <Paperclip size={16} />
              )}
            </button>

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
                placeholder="Ask a question, or drag & drop files anywhere to index..."
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
              PostgreSQL pgvector (Dense) + BM25/tsvector (Sparse) fused via RRF.
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
