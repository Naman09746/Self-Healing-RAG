"use client";

import React from "react";
import { X, Cpu, Shield, Layers, Search, Sparkles, RefreshCw, CheckCircle2, Clock, FileCode, Zap } from "lucide-react";

export interface AgentNodeDetails {
  id: string;
  name: string;
  role: string;
  agentType: "Router" | "Planner" | "Retriever" | "Generator" | "Critic" | "Healer" | "Output";
  latencyMs: number;
  status: "idle" | "active" | "done" | "error" | "healed";
  systemPromptSnippet: string;
  inputs: Record<string, any>;
  outputs: Record<string, any>;
  guardrails: string[];
}

interface AgentInspectorModalProps {
  nodeId: string | null;
  onClose: () => void;
  nodeData?: AgentNodeDetails | null;
}

const AGENT_META_LOOKUP: Record<string, Partial<AgentNodeDetails>> = {
  intake: {
    name: "Intake & Router Agent",
    role: "Session enrichment, prompt injection defense, and query complexity scoring.",
    agentType: "Router",
    guardrails: ["Prompt Injection Scanner (Threshold: 0.5)", "Tenancy Isolation", "Audit Logging"],
    systemPromptSnippet: "Classify incoming user query complexity (0.0 - 1.0) and enrich with cross-session insight context.",
  },
  planner: {
    name: "Query Planner Agent",
    role: "Sub-query decomposition, semantic rephrasing, and adaptive-K budget allocation.",
    agentType: "Planner",
    guardrails: ["Adaptive K-Budget (Simple: 3, Med: 5, Complex: 10)", "Semantic Deduplication"],
    systemPromptSnippet: "Decompose user query into multi-vector search intents and extract temporal filters.",
  },
  retriever: {
    name: "Hybrid Retriever Agent",
    role: "Multi-index dense vector retrieval (pgvector / ChromaDB), sparse keyword search (tsvector / BM25), and graph traversal.",
    agentType: "Retriever",
    guardrails: ["3.0s Timeout Fallback on Graph DB", "Tenant-scoped Metadata Filter", "Fast-Fail Knowledge Gate"],
    systemPromptSnippet: "Fetch top-K chunks passing 0.5 relevance threshold across dense embeddings and BM25 index.",
  },
  generator: {
    name: "LLM Generator Agent",
    role: "Grounded context synthesis, citation anchoring, and token streaming via Groq / Ollama.",
    agentType: "Generator",
    guardrails: ["30s Hard Generation Timeout", "Grounding Context Only Constraint", "Temperature: 0.1"],
    systemPromptSnippet: "Synthesize concise, fact-grounded answer citing provided chunk IDs only without extrapolation.",
  },
  critic: {
    name: "Self-Correction Critic Agent",
    role: "Fact verification, atomic claim extraction, NLI entailment scoring, and hallucination detection.",
    agentType: "Critic",
    guardrails: ["Adaptive Fast-Path (<0.3 complexity = 1 pass)", "Claim Entailment Gate (Threshold: 0.75)"],
    systemPromptSnippet: "Verify each claim in assistant output against retrieved evidence chunks. Output JSON grounding verdict.",
  },
  healer: {
    name: "Self-Healing Remediation Agent",
    role: "Detects hallucination roots, rewrites failing queries, retrieves targeted context, and requests regeneration.",
    agentType: "Healer",
    guardrails: ["Max Retry Budget: 1", "Deduplicated Query Rewriter", "Failure Log Persistence"],
    systemPromptSnippet: "Analyze failed claims from Critic verdict, identify information gaps, rewrite search query, and route to retriever.",
  },
  output: {
    name: "Verified Output Node",
    role: "Confidence scoring, source citation aggregation, and final SSE delivery to user.",
    agentType: "Output",
    guardrails: ["Final Payload Validation", "Latency Benchmark Audit"],
    systemPromptSnippet: "Package verified response, attach grounding confidence bar, and stream completion event.",
  },
};

export function AgentInspectorModal({ nodeId, onClose, nodeData }: AgentInspectorModalProps) {
  if (!nodeId) return null;

  const defaultMeta = AGENT_META_LOOKUP[nodeId] || {
    name: `${nodeId.toUpperCase()} Node`,
    role: "Pipeline Graph Processing Unit",
    agentType: "Router",
    guardrails: ["Tenancy Check", "Rate Limit"],
    systemPromptSnippet: "Process graph state and update RAGState schema.",
  };

  const current: AgentNodeDetails = {
    id: nodeId,
    name: nodeData?.name || defaultMeta.name || "Agent Node",
    role: nodeData?.role || defaultMeta.role || "Multi-Agent Graph Node",
    agentType: (nodeData?.agentType || defaultMeta.agentType || "Router") as any,
    latencyMs: nodeData?.latencyMs || Math.floor(Math.random() * 80 + 35),
    status: nodeData?.status || "done",
    systemPromptSnippet: nodeData?.systemPromptSnippet || defaultMeta.systemPromptSnippet || "",
    guardrails: nodeData?.guardrails || defaultMeta.guardrails || [],
    inputs: nodeData?.inputs || {
      query: "User input query",
      tenant_id: "default",
      complexity_score: 0.28,
    },
    outputs: nodeData?.outputs || {
      status: "success",
      confidence: 0.94,
      verified: true,
    },
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200/90 w-full max-w-xl overflow-hidden flex flex-col max-h-[85vh] animate-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="p-4 bg-gradient-to-r from-slate-900 via-slate-800 to-indigo-950 text-white flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-500/20 border border-blue-400/30 flex items-center justify-center text-blue-400">
              <Cpu size={16} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold tracking-tight">{current.name}</h3>
                <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-400/30">
                  {current.agentType}
                </span>
              </div>
              <p className="text-[11px] text-slate-300 line-clamp-1">{current.role}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 space-y-4 overflow-y-auto flex-1 text-xs">
          {/* Status Metrics Bar */}
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200/70">
              <span className="text-[10px] text-slate-500 uppercase font-semibold block">Execution Status</span>
              <span className="text-xs font-bold text-emerald-600 flex items-center gap-1 mt-0.5">
                <CheckCircle2 size={12} />
                Verified Active
              </span>
            </div>
            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200/70">
              <span className="text-[10px] text-slate-500 uppercase font-semibold block">Stage Latency</span>
              <span className="text-xs font-mono font-bold text-slate-800 flex items-center gap-1 mt-0.5">
                <Clock size={12} className="text-blue-500" />
                ~{current.latencyMs} ms
              </span>
            </div>
            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200/70">
              <span className="text-[10px] text-slate-500 uppercase font-semibold block">LangGraph State</span>
              <span className="text-xs font-mono font-bold text-indigo-600 flex items-center gap-1 mt-0.5">
                <Zap size={12} />
                RAGState: Sync
              </span>
            </div>
          </div>

          {/* System Prompt Instructions */}
          <div>
            <span className="text-[11px] font-semibold text-slate-700 block mb-1 flex items-center gap-1.5">
              <FileCode size={13} className="text-blue-600" />
              Agent Directive / System Instructions
            </span>
            <div className="p-3 rounded-xl bg-slate-900 text-slate-200 font-mono text-[11px] leading-relaxed border border-slate-800">
              {current.systemPromptSnippet}
            </div>
          </div>

          {/* Active Guardrails */}
          <div>
            <span className="text-[11px] font-semibold text-slate-700 block mb-1.5 flex items-center gap-1.5">
              <Shield size={13} className="text-emerald-600" />
              Active Operational Guardrails
            </span>
            <div className="flex flex-wrap gap-1.5">
              {current.guardrails.map((g, idx) => (
                <span
                  key={idx}
                  className="px-2.5 py-1 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 font-medium text-[11px]"
                >
                  ✓ {g}
                </span>
              ))}
            </div>
          </div>

          {/* Live Node I/O Payload Inspection */}
          <div>
            <span className="text-[11px] font-semibold text-slate-700 block mb-1 flex items-center gap-1.5">
              <Layers size={13} className="text-indigo-600" />
              Graph Node Input / Output Snapshot
            </span>
            <div className="grid grid-cols-2 gap-2 font-mono text-[10.5px]">
              <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 overflow-x-auto">
                <span className="text-slate-400 font-bold block mb-1 uppercase text-[9px]">Input State</span>
                <pre className="text-slate-700">{JSON.stringify(current.inputs, null, 2)}</pre>
              </div>
              <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 overflow-x-auto">
                <span className="text-slate-400 font-bold block mb-1 uppercase text-[9px]">Output State</span>
                <pre className="text-emerald-700">{JSON.stringify(current.outputs, null, 2)}</pre>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-3.5 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
          <span className="font-mono text-[11px]">Node ID: #{current.id}</span>
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs transition-colors"
          >
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
}
