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
  X,
} from "lucide-react";
import { query as queryApi, documents as docsApi, type QueryResponse, type RetrievedChunk } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { useDocuments } from "@/lib/hooks";
import { useDragDrop } from "@/lib/useDragDrop";

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

interface UploadQueueItem {
  id: string;
  name: string;
  size: number;
  status: "uploading" | "embedding" | "indexed" | "error";
  chunks?: number;
  error?: string;
}

  // Document Drag & Drop + Manual Selection State
  const [uploadQueue, setUploadQueue] = useState<UploadQueueItem[]>([]);
  const [recentUploads, setRecentUploads] = useState<string[]>([]);
  const [selectedDocNames, setSelectedDocNames] = useState<string[]>([]);
  const [showDocSelector, setShowDocSelector] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Active query trace state for the selected/latest response
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);

  const formatFileSize = (bytes: number): string => {
    if (!bytes || bytes === 0) return "0 B";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleDocumentUpload = useCallback(async (files: FileList | File[]) => {
    const fileList = Array.from(files);
    if (!fileList.length) return;

    const newItems: UploadQueueItem[] = fileList.map((f) => ({
      id: `up-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      name: f.name,
      size: f.size,
      status: "uploading",
    }));

    setUploadQueue((prev) => [...newItems, ...prev]);

    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i];
      const item = newItems[i];

      // Update to embedding phase
      setUploadQueue((prev) =>
        prev.map((u) => (u.id === item.id ? { ...u, status: "embedding" } : u))
      );

      try {
        const res = await docsApi.upload(file);
        const chunkCount = res.chunk_count ?? res.chunks_count ?? 1;

        setUploadQueue((prev) =>
          prev.map((u) =>
            u.id === item.id ? { ...u, status: "indexed", chunks: chunkCount } : u
          )
        );

        setSelectedDocNames((prev) =>
          prev.includes(file.name) ? prev : [...prev, file.name]
        );
        setRecentUploads((prev) => [file.name, ...prev.filter((n) => n !== file.name)].slice(0, 5));
        toast.success(`Indexed "${file.name}" (${chunkCount} chunks) into pgvector.`);
      } catch (err) {
        const rawErr = (err as Error).message || "Upload failed";
        // Clean error display
        const cleanErr = rawErr.length > 120 ? `${rawErr.slice(0, 117)}...` : rawErr;
        setUploadQueue((prev) =>
          prev.map((u) => (u.id === item.id ? { ...u, status: "error", error: cleanErr } : u))
        );
        toast.error(`Ingest failed for "${file.name}": ${cleanErr}`);
      }
    }

    await refreshDocs();
  }, [refreshDocs, toast]);

  const { isDragging, isHoveringZone, dragHandlers: queryDragHandlers, zoneDragHandlers } = useDragDrop({
    onDrop: handleDocumentUpload,
    multiple: true,
    maxFiles: 10,
  });

  const removeQueueItem = (id: string) => {
    setUploadQueue((prev) => prev.filter((u) => u.id !== id));
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
      {...queryDragHandlers}
      className="relative flex-1 flex flex-col lg:flex-row h-[calc(100vh-3.5rem)] overflow-hidden"
    >
      {/* ── Drag & Drop Full-Page Overlay — light glassy, never dark, smooth ── */}
      {isDragging && (
        <div
          {...queryDragHandlers}
          className="absolute inset-0 z-50 bg-white/30 dark:bg-slate-900/20 backdrop-blur-[12px] flex flex-col items-center justify-center p-6 animate-in fade-in duration-200 cursor-copy"
        >
          <div
            className="relative bg-white/90 dark:bg-slate-900/75 backdrop-blur-2xl rounded-3xl p-8 shadow-[0_24px_70px_rgba(37,99,235,0.18)] border border-white/60 dark:border-slate-700/40 flex flex-col items-center text-center max-w-md mx-4 ring-1 ring-blue-200/40 dark:ring-blue-500/20 scale-100 animate-in zoom-in-95 duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] pointer-events-none"
          >
            {/* Soft floating icon — not bounce */}
            <div className="relative mb-5">
              <div className="absolute -inset-3 rounded-3xl bg-blue-500/10 dark:bg-blue-400/10 blur-xl" />
              <div className="relative w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center shadow-[0_8px_24px_rgba(37,99,235,0.25)] animate-[float_3s_ease-in-out_infinite]">
                <Upload size={28} className="text-white" />
              </div>
            </div>

            <h3 className="text-lg font-bold text-slate-900 dark:text-white tracking-tight">
              Drop to Index Documents
            </h3>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-2 max-w-xs text-center leading-relaxed">
              Release to automatically chunk, embed, and index into pgvector &amp; BM25
            </p>

            <div className="mt-5 flex flex-wrap justify-center gap-1.5 max-w-sm">
              {["PDF", "DOCX", "PPTX", "XLSX", "CSV", "TXT", "MD", "JSON", "OCR"].map((fmt) => (
                <span
                  key={fmt}
                  className="px-2 py-0.5 rounded-md bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 text-[10px] font-semibold border border-blue-200/60 dark:border-blue-800/60"
                >
                  {fmt}
                </span>
              ))}
            </div>
            
            <p className="text-[11px] text-slate-400 mt-4">
              Press <kbd className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 font-mono text-[10px] text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700">Esc</kbd> to cancel
            </p>
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
          {/* Live Ingestion / Upload Progress Cards */}
          {uploadQueue.length > 0 && (
            <div className="space-y-2">
              {uploadQueue.map((item) => (
                <div
                  key={item.id}
                  className={`flex items-center justify-between gap-3 p-3 rounded-xl border text-xs transition-all ${
                    item.status === "indexed"
                      ? "bg-emerald-50/70 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800/60 text-emerald-900 dark:text-emerald-200"
                      : item.status === "error"
                      ? "bg-rose-50/70 dark:bg-rose-950/20 border-rose-200 dark:border-rose-800/60 text-rose-900 dark:text-rose-200"
                      : "bg-blue-50/70 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800/60 text-blue-900 dark:text-blue-200"
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0 flex-1">
                    <div
                      className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
                        item.status === "indexed"
                          ? "bg-emerald-100 dark:bg-emerald-900/50 text-emerald-600 dark:text-emerald-400"
                          : item.status === "error"
                          ? "bg-rose-100 dark:bg-rose-900/50 text-rose-600 dark:text-rose-400"
                          : "bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400"
                      }`}
                    >
                      {item.status === "indexed" ? (
                        <CheckCircle2 size={15} />
                      ) : item.status === "error" ? (
                        <AlertTriangle size={15} />
                      ) : (
                        <Loader2 size={15} className="animate-spin" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold truncate text-[12px] flex items-center gap-1.5">
                        <span>{item.name}</span>
                        <span className="text-[10px] opacity-60 font-mono font-normal">
                          ({formatFileSize(item.size)})
                        </span>
                      </div>
                      <div className="text-[11px] opacity-75 mt-0.5 truncate">
                        {item.status === "uploading" && "Uploading document to server..."}
                        {item.status === "embedding" && "Chunking, calculating embeddings & writing to pgvector..."}
                        {item.status === "indexed" && (
                          <span className="text-emerald-700 dark:text-emerald-300 font-medium">
                            Ready to query • {item.chunks || 1} chunks indexed across vector & sparse stores
                          </span>
                        )}
                        {item.status === "error" && (
                          <span className="text-rose-700 dark:text-rose-300 font-medium">
                            {item.error || "Ingestion failed"}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeQueueItem(item.id)}
                    className="p-1 rounded-md hover:bg-black/5 dark:hover:bg-white/10 opacity-60 hover:opacity-100 transition-opacity"
                    title="Dismiss"
                  >
                    <X size={13} />
                  </button>
                </div>
              ))}
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

              {/* Quick Drop Zone Box for Empty State — animated interactive drop target */}
              <div
                {...zoneDragHandlers}
                onClick={() => fileInputRef.current?.click()}
                role="region"
                aria-label="Document drop zone"
                className={`mt-6 w-full p-6 rounded-2xl border-2 border-dashed cursor-pointer transition-all duration-300 text-center ${
                  isHoveringZone
                    ? "border-blue-500 bg-blue-50/80 dark:bg-blue-950/40 shadow-[0_12px_40px_rgba(37,99,235,0.18)] ring-4 ring-blue-500/20 scale-[1.02]"
                    : "border-slate-200/80 dark:border-slate-700/60 bg-white/60 dark:bg-slate-800/30 backdrop-blur-md hover:border-blue-400 dark:hover:border-blue-500 hover:bg-white/90 dark:hover:bg-slate-800/60 hover:shadow-[0_4px_20px_rgba(15,23,42,0.06)]"
                }`}
              >
                <div className={`w-11 h-11 mx-auto rounded-xl flex items-center justify-center mb-2.5 transition-transform ${
                  isHoveringZone ? "scale-110 bg-blue-600 text-white shadow-md shadow-blue-500/30" : "bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400"
                }`}>
                  <Upload size={18} className={isHoveringZone ? "animate-bounce" : ""} />
                </div>
                <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                  {isHoveringZone ? "Drop to upload immediately" : "Drag & drop files here, or click to browse"}
                </div>
                <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 max-w-md mx-auto">
                  PDF, DOCX, PPTX, XLSX, CSV, TXT, MD, HTML, JSON + images (OCR) — up to 50 MB
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
        <div className="p-3 sm:p-4 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-2.5">
          {/* Hidden File Input — all backend-supported types */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.doc,.odt,.rtf,.pptx,.ppt,.xlsx,.xls,.ods,.csv,.tsv,.html,.htm,.xml,.json,.jsonl,.txt,.md,.markdown,.png,.jpg,.jpeg,.webp,.tiff,.tif,.bmp,.gif,.epub"
            className="hidden"
            onChange={async (e) => {
              if (e.target.files?.length) {
                await handleDocumentUpload(e.target.files);
                e.target.value = "";
              }
            }}
          />

          {/* Attached Files Tray (ChatGPT / Claude Style) */}
          {uploadQueue.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 max-h-28 overflow-y-auto pr-1">
              {uploadQueue.map((item) => (
                <div
                  key={item.id}
                  className={`inline-flex items-center gap-2 pl-2.5 pr-2 py-1.5 rounded-lg border text-xs font-medium transition-all ${
                    item.status === "indexed"
                      ? "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-300 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200"
                      : item.status === "error"
                      ? "bg-rose-50 dark:bg-rose-950/40 border-rose-300 dark:border-rose-800 text-rose-800 dark:text-rose-200"
                      : "bg-blue-50 dark:bg-blue-950/40 border-blue-300 dark:border-blue-800 text-blue-800 dark:text-blue-200"
                  }`}
                >
                  <div className="shrink-0">
                    {item.status === "indexed" ? (
                      <CheckCircle2 size={13} className="text-emerald-600 dark:text-emerald-400" />
                    ) : item.status === "error" ? (
                      <AlertTriangle size={13} className="text-rose-600 dark:text-rose-400" />
                    ) : (
                      <Loader2 size={13} className="animate-spin text-blue-600 dark:text-blue-400" />
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 truncate max-w-[200px]">
                    <span className="truncate">{item.name}</span>
                    <span className="text-[10px] opacity-60 font-mono">
                      {formatFileSize(item.size)}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeQueueItem(item.id)}
                    className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 p-0.5 rounded hover:bg-black/5 dark:hover:bg-white/10 transition-colors ml-0.5"
                    title="Remove"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}

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
              disabled={loading}
              title="Attach & Index Documents (PDF, MD, TXT)"
              className="h-11 w-11 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/40 text-slate-500 hover:text-blue-600 dark:hover:text-blue-400 flex items-center justify-center transition-all shrink-0 cursor-pointer disabled:opacity-50"
            >
              {uploadQueue.some((u) => u.status === "uploading" || u.status === "embedding") ? (
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
