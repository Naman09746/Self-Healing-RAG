"use client";

import { useState, useCallback } from "react";
import {
  Workflow,
  Play,
  RotateCcw,
  Layers,
  Sparkles,
  Shield,
  Clock,
  CheckCircle2,
  RefreshCw,
  Cpu,
  AlertTriangle,
} from "lucide-react";
import LivePipeline from "@/components/LivePipeline";
import { AgentInspectorModal } from "@/components/AgentInspectorModal";

const PIPELINE_TIMELINE_STEPS = [
  { id: "intake", name: "Intake & Router", typicalMs: 24, role: "Complexity score & security guard" },
  { id: "planner", name: "Query Planner", typicalMs: 38, role: "Adaptive K & intent decomposition" },
  { id: "retriever", name: "Hybrid Retriever", typicalMs: 112, role: "ChromaDB dense + BM25 + Neo4j" },
  { id: "generator", name: "LLM Generator", typicalMs: 340, role: "Context synthesis & token streaming" },
  { id: "critic", name: "Critic & Grader", typicalMs: 86, role: "Atomic claim verification" },
  { id: "healer", name: "Self-Healer Loop", typicalMs: 220, role: "Automated rewrite on low grounding" },
  { id: "output", name: "Verified Output", typicalMs: 12, role: "Delivery with citations & audit trail" },
];

export default function PipelinePage() {
  const [activePhase, setActivePhase] = useState<string | null>(null);
  const [phaseStatus, setPhaseStatus] = useState<Record<string, "idle" | "active" | "done" | "error" | "healed">>({});
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>("retriever");
  const [isSimulating, setIsSimulating] = useState(false);

  // Simulation runner to inspect pipeline state dynamically
  const runSimulation = useCallback((withHeal = false) => {
    if (isSimulating) return;
    setIsSimulating(true);
    setPhaseStatus({});

    const steps = withHeal
      ? ["intake", "planner", "retriever", "generator", "critic", "healer", "retriever", "generator", "critic", "output"]
      : ["intake", "planner", "retriever", "generator", "critic", "output"];

    let index = 0;
    const interval = setInterval(() => {
      if (index >= steps.length) {
        clearInterval(interval);
        setActivePhase(null);
        setIsSimulating(false);
        return;
      }

      const step = steps[index];
      setActivePhase(step);

      setPhaseStatus((prev) => {
        const next = { ...prev };
        if (step === "healer") {
          next["critic"] = "error";
          next["healer"] = "healed";
        } else {
          next[step] = "active";
          if (index > 0 && steps[index - 1] !== "healer") {
            next[steps[index - 1]] = "done";
          }
        }
        return next;
      });

      index++;
    }, 700);
  }, [isSimulating]);

  const resetPipeline = () => {
    setActivePhase(null);
    setPhaseStatus({});
  };

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-3.5rem)] overflow-hidden">
      {/* 1. Header Toolbar */}
      <div className="h-14 px-4 sm:px-6 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between shrink-0">
        <div>
          <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Workflow size={16} className="text-blue-600" />
            <span>AI Pipeline Execution Graph</span>
          </h2>
          <p className="text-[11px] text-slate-500 dark:text-slate-400">
            Inspect LangGraph nodes, routing transitions, and self-healing loops. Click any node to inspect details.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => runSimulation(false)}
            disabled={isSimulating}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold text-xs shadow-xs transition-colors cursor-pointer"
          >
            <Play size={12} />
            <span>Simulate Flow</span>
          </button>

          <button
            onClick={() => runSimulation(true)}
            disabled={isSimulating}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50 hover:bg-amber-100 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 font-semibold text-xs transition-colors cursor-pointer"
          >
            <RefreshCw size={12} />
            <span>Simulate Self-Heal</span>
          </button>

          <button
            onClick={resetPipeline}
            disabled={isSimulating}
            className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 transition-colors"
            title="Reset states"
          >
            <RotateCcw size={14} />
          </button>
        </div>
      </div>

      {/* 2. Main Stage: Large LangGraph Canvas */}
      <div className="flex-1 relative bg-slate-50/70 dark:bg-slate-950 min-h-0">
        <LivePipeline
          activePhase={activePhase}
          phaseStatus={phaseStatus}
          onNodeClick={(id) => setSelectedNodeId(id)}
        />

        {/* Legend Overlay */}
        <div className="absolute top-4 left-4 p-3 rounded-xl bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border border-slate-200 dark:border-slate-800 shadow-sm text-xs space-y-2 pointer-events-none">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Graph Legend
          </div>
          <div className="flex items-center gap-2 text-[11px] text-slate-600 dark:text-slate-400">
            <span className="w-2.5 h-2.5 rounded-sm bg-blue-500" />
            <span>Primary Execution Path</span>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-slate-600 dark:text-slate-400">
            <span className="w-2.5 h-2.5 rounded-sm bg-amber-500" />
            <span>Self-Heal Query Rewrite</span>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-slate-600 dark:text-slate-400">
            <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500" />
            <span>Grounded Verification Gate</span>
          </div>
        </div>
      </div>

      {/* 3. Bottom Strip: Execution Timeline & Typical Latencies */}
      <div className="h-20 px-6 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 flex items-center overflow-x-auto shrink-0">
        <div className="flex items-center gap-6 min-w-max">
          <div className="text-xs font-bold text-slate-700 dark:text-slate-300">
            Node Stages:
          </div>
          {PIPELINE_TIMELINE_STEPS.map((step, idx) => (
            <button
              key={step.id}
              onClick={() => setSelectedNodeId(step.id)}
              className={`flex items-center gap-2.5 text-xs p-1.5 rounded-lg transition-all text-left ${
                selectedNodeId === step.id
                  ? "bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-400 font-semibold"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100"
              }`}
            >
              <div className="w-5 h-5 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center font-mono text-[10px]">
                {idx + 1}
              </div>
              <div>
                <div className="text-xs font-medium">{step.name}</div>
                <div className="text-[10px] font-mono text-slate-400">~{step.typicalMs}ms</div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Interactive Node Inspector Modal */}
      <AgentInspectorModal
        nodeId={selectedNodeId}
        onClose={() => setSelectedNodeId(null)}
      />
    </div>
  );
}
