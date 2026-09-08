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
  phaseStatus?: Record<string, "idle" | "active" | "done" | "error">;
}

const BASE_NODES: Node[] = [
  {
    id: "intake",
    type: "input",
    data: { label: "Intake" },
    position: { x: 200, y: 0 },
  },
  { id: "planner", data: { label: "Planner" }, position: { x: 200, y: 90 } },
  { id: "retriever", data: { label: "Retriever" }, position: { x: 200, y: 180 } },
  { id: "generator", data: { label: "Generator" }, position: { x: 200, y: 270 } },
  { id: "critic", data: { label: "Critic" }, position: { x: 200, y: 360 } },
  {
    id: "healer",
    data: { label: "Healer" },
    position: { x: 420, y: 180 },
  },
  {
    id: "output",
    type: "output",
    data: { label: "Output" },
    position: { x: 200, y: 450 },
  },
];

const BASE_EDGES: Edge[] = [
  { id: "e-intake-planner", source: "intake", target: "planner", animated: false, markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 } },
  { id: "e-planner-retriever", source: "planner", target: "retriever", animated: false, markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 } },
  { id: "e-retriever-generator", source: "retriever", target: "generator", animated: false, markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 } },
  { id: "e-generator-critic", source: "generator", target: "critic", animated: false, markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 } },
  { id: "e-critic-healer", source: "critic", target: "healer", label: "heal", style: { stroke: "#ef4444" }, markerEnd: { type: MarkerType.ArrowClosed, color: "#ef4444" } },
  { id: "e-healer-retriever", source: "healer", target: "retriever", label: "retry", animated: false, style: { stroke: "#ef4444" }, markerEnd: { type: MarkerType.ArrowClosed, color: "#ef4444" } },
  { id: "e-critic-output", source: "critic", target: "output", label: "verified", style: { stroke: "#22c55e" }, markerEnd: { type: MarkerType.ArrowClosed, color: "#22c55e" } },
];

const PHASE_COLORS: Record<string, string> = {
  idle: "#f1f5f9",
  active: "#2563eb",
  done: "#059669",
  error: "#dc2626",
};

const PHASE_BORDER_COLORS: Record<string, string> = {
  idle: "#cbd5e1",
  active: "#3b82f6",
  done: "#10b981",
  error: "#ef4444",
};

export default function LivePipeline({ activePhase, phaseStatus }: LivePipelineProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState(BASE_NODES);
  const [edges, setEdges, onEdgesChange] = useEdgesState(BASE_EDGES);

  useEffect(() => {
    setNodes((nds) =>
      nds.map((node) => {
        const status = phaseStatus?.[node.id] || (activePhase === node.id ? "active" : "idle");
        const color = PHASE_COLORS[status];
        const borderColor = PHASE_BORDER_COLORS[status];

        return {
          ...node,
          style: {
            background: status === "active" ? "#eff6ff" : status === "done" ? "#ecfdf5" : status === "error" ? "#fef2f2" : "#ffffff",
            color: status === "active" ? "#1d4ed8" : status === "done" ? "#059669" : status === "error" ? "#dc2626" : "#334155",
            border: `1.5px solid ${borderColor}`,
            borderRadius: "8px",
            padding: "8px 16px",
            fontSize: "12px",
            fontWeight: status === "active" ? 600 : 500,
            fontFamily: "var(--font-sans)",
            transition: "all 0.25s ease",
            boxShadow: status === "active" ? "0 4px 12px rgba(37, 99, 235, 0.15)" : "0 1px 3px rgba(15, 23, 42, 0.05)",
            width: 125,
            textAlign: "center" as const,
          },
        };
      })
    );
  }, [activePhase, phaseStatus, setNodes]);

  useEffect(() => {
    setEdges((eds) =>
      eds.map((edge) => {
        const isActiveHealing = activePhase === "healer" && (edge.id === "e-critic-healer" || edge.id === "e-healer-retriever");
        const isActiveForward = !isActiveHealing && edge.target === activePhase;
        const isDone = phaseStatus && edge.target && phaseStatus[edge.target] === "done";

        return {
          ...edge,
          animated: isActiveForward || isActiveHealing,
          style: {
            ...(edge.style as object),
            stroke: isDone ? "#059669" : isActiveForward || isActiveHealing ? "#2563eb" : "#94a3b8",
            strokeWidth: isActiveForward || isActiveHealing ? 2 : 1.2,
            opacity: isActiveForward || isActiveHealing ? 1 : 0.7,
            transition: "all 0.25s ease",
          },
          labelStyle: {
            fontSize: "10px",
            fill: isActiveHealing ? "#dc2626" : "#64748b",
            fontFamily: "var(--font-mono)",
            fontWeight: 600,
          },
        };
      })
    );
  }, [activePhase, phaseStatus, setEdges]);

  return (
    <div className="w-full h-full border border-slate-200/80 bg-slate-50/50 rounded-xl overflow-hidden shadow-xs">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        minZoom={0.5}
        maxZoom={2}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag={false}
        zoomOnScroll={false}
      >
        <Background color="#cbd5e1" gap={20} size={1} />
        <Controls showInteractive={false} className="!bg-white !border !border-slate-200 !shadow-xs [&>button]:!bg-white [&>button]:!border-b [&>button]:!border-slate-200 [&>button]:!text-slate-600 [&>button]:!rounded-none [&>button]:!w-7 [&>button]:!h-7" />
      </ReactFlow>
    </div>
  );
}
