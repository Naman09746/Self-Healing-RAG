"use client";

import React, { useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
} from "@xyflow/react";
import type { Node, Edge } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

interface LivePipelineProps {
  activePhase?: string | null;
  phaseStatus?: Record<string, "idle" | "active" | "done" | "error" | "healed">;
  onNodeClick?: (nodeId: string) => void;
}

const BASE_NODES: Node[] = [
  {
    id: "intake",
    type: "input",
    data: { label: "1. Intake & Router" },
    position: { x: 200, y: 0 },
  },
  { id: "planner", data: { label: "2. Query Planner" }, position: { x: 200, y: 85 } },
  { id: "retriever", data: { label: "3. Hybrid Retriever" }, position: { x: 200, y: 170 } },
  { id: "generator", data: { label: "4. LLM Generator" }, position: { x: 200, y: 255 } },
  { id: "critic", data: { label: "5. Critic & Grader" }, position: { x: 200, y: 340 } },
  {
    id: "healer",
    data: { label: "↺ Self-Healer Loop" },
    position: { x: 420, y: 255 },
  },
  {
    id: "output",
    type: "output",
    data: { label: "6. Verified Output" },
    position: { x: 200, y: 425 },
  },
];

const BASE_EDGES: Edge[] = [
  { id: "e-intake-planner", source: "intake", target: "planner", animated: false, markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14 } },
  { id: "e-planner-retriever", source: "planner", target: "retriever", animated: false, markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14 } },
  { id: "e-retriever-generator", source: "retriever", target: "generator", animated: false, markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14 } },
  { id: "e-generator-critic", source: "generator", target: "critic", animated: false, markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14 } },
  { id: "e-critic-healer", source: "critic", target: "healer", label: "hallucination detected", style: { stroke: "#ef4444", strokeDasharray: "4,4" }, markerEnd: { type: MarkerType.ArrowClosed, color: "#ef4444" } },
  { id: "e-healer-retriever", source: "healer", target: "retriever", label: "rewrite & retry", animated: false, style: { stroke: "#f59e0b", strokeDasharray: "4,4" }, markerEnd: { type: MarkerType.ArrowClosed, color: "#f59e0b" } },
  { id: "e-critic-output", source: "critic", target: "output", label: "grounded ✓", style: { stroke: "#10b981" }, markerEnd: { type: MarkerType.ArrowClosed, color: "#10b981" } },
];

const PHASE_COLORS: Record<string, string> = {
  idle: "#ffffff",
  active: "#eff6ff",
  done: "#ecfdf5",
  error: "#fef2f2",
  healed: "#fffbeb",
};

const PHASE_BORDER_COLORS: Record<string, string> = {
  idle: "#e2e8f0",
  active: "#2563eb",
  done: "#10b981",
  error: "#ef4444",
  healed: "#f59e0b",
};

export default function LivePipeline({ activePhase, phaseStatus, onNodeClick }: LivePipelineProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState(BASE_NODES);
  const [edges, setEdges, onEdgesChange] = useEdgesState(BASE_EDGES);

  useEffect(() => {
    setNodes((nds) =>
      nds.map((node) => {
        const isCurrent = activePhase === node.id;
        const status = phaseStatus?.[node.id] || (isCurrent ? "active" : "idle");
        const borderColor = PHASE_BORDER_COLORS[status] || "#e2e8f0";
        const isHealerNode = node.id === "healer";

        return {
          ...node,
          style: {
            background: isHealerNode && isCurrent ? "#fff1f2" : isCurrent ? "#eff6ff" : status === "done" ? "#ecfdf5" : "#ffffff",
            color: isHealerNode && isCurrent ? "#e11d48" : isCurrent ? "#1d4ed8" : status === "done" ? "#047857" : "#334155",
            border: isCurrent ? `2px solid ${isHealerNode ? "#f43f5e" : "#2563eb"}` : `1.5px solid ${borderColor}`,
            borderRadius: "10px",
            padding: "8px 12px",
            fontSize: "11px",
            fontWeight: isCurrent ? 700 : 600,
            fontFamily: "var(--font-sans)",
            transition: "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
            boxShadow: isCurrent
              ? isHealerNode
                ? "0 0 16px rgba(244, 63, 94, 0.35)"
                : "0 0 16px rgba(37, 99, 235, 0.3)"
              : "0 1px 3px rgba(15, 23, 42, 0.05)",
            width: 142,
            textAlign: "center" as const,
            cursor: "pointer",
            transform: isCurrent ? "scale(1.04)" : "scale(1)",
          },
        };
      })
    );
  }, [activePhase, phaseStatus, setNodes]);

  useEffect(() => {
    setEdges((eds) =>
      eds.map((edge) => {
        const isHealingFlow = activePhase === "healer" && (edge.id === "e-critic-healer" || edge.id === "e-healer-retriever");
        const isForwardActive = !isHealingFlow && edge.target === activePhase;
        const isVerified = edge.id === "e-critic-output" && activePhase === "output";

        return {
          ...edge,
          animated: isForwardActive || isHealingFlow || isVerified,
          style: {
            ...(edge.style as object),
            stroke: isHealingFlow ? "#ef4444" : isVerified ? "#10b981" : isForwardActive ? "#2563eb" : "#94a3b8",
            strokeWidth: isHealingFlow || isForwardActive || isVerified ? 2.5 : 1.2,
            opacity: isHealingFlow || isForwardActive || isVerified ? 1 : 0.6,
            transition: "all 0.3s ease",
          },
          labelStyle: {
            fontSize: "9.5px",
            fill: isHealingFlow ? "#dc2626" : isVerified ? "#059669" : "#64748b",
            fontFamily: "var(--font-mono)",
            fontWeight: 600,
          },
        };
      })
    );
  }, [activePhase, phaseStatus, setEdges]);

  return (
    <div className="w-full h-full border border-slate-200/80 bg-slate-50/50 rounded-xl overflow-hidden shadow-xs relative">
      <div className="absolute top-2 right-2 z-10 text-[10px] font-mono text-slate-400 bg-white/80 backdrop-blur-xs px-2 py-0.5 rounded border border-slate-200 pointer-events-none">
        Click node to inspect
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={(e, node) => onNodeClick && onNodeClick(node.id)}
        fitView
        minZoom={0.6}
        maxZoom={1.5}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={true}
        panOnDrag={false}
        zoomOnScroll={false}
      >
        <Background color="#cbd5e1" gap={18} size={1} />
        <Controls showInteractive={false} className="!bg-white !border !border-slate-200 !shadow-xs [&>button]:!bg-white [&>button]:!border-b [&>button]:!border-slate-200 [&>button]:!text-slate-600 [&>button]:!rounded-none [&>button]:!w-6 [&>button]:!h-6" />
      </ReactFlow>
    </div>
  );
}
