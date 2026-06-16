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
  idle: "#18181b",
  active: "#6366f1",
  done: "#22c55e",
  error: "#ef4444",
};

const PHASE_BORDER_COLORS: Record<string, string> = {
  idle: "#27272a",
  active: "#818cf8",
  done: "#22c55e",
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
            background: color + "15",
            color: status === "active" ? "#e4e4ed" : status === "done" ? "#22c55e" : status === "error" ? "#ef4444" : "#8b8b9e",
            border: `1px solid ${borderColor}40`,
            borderRadius: "10px",
            padding: "10px 18px",
            fontSize: "12px",
            fontWeight: status === "active" ? 600 : 500,
            fontFamily: "var(--font-sans)",
            transition: "all 0.3s ease",
            boxShadow: status === "active" ? `0 0 20px ${color}30` : "none",
            width: 120,
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
            stroke: isDone ? "#22c55e" : isActiveForward || isActiveHealing ? "#818cf8" : "#27272a",
            strokeWidth: isActiveForward || isActiveHealing ? 2 : 1,
            opacity: isActiveForward || isActiveHealing ? 1 : 0.5,
            transition: "all 0.3s ease",
          },
          labelStyle: {
            fontSize: "9px",
            fill: isActiveHealing ? "#ef4444" : "#525266",
            fontFamily: "var(--font-mono)",
            fontWeight: 600,
          },
        };
      })
    );
  }, [activePhase, phaseStatus, setEdges]);

  return (
    <div className="w-full h-full" style={{ background: "#07070b", borderRadius: "12px" }}>
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
        <Background color="rgba(255,255,255,0.03)" gap={24} />
        <Controls showInteractive={false} className="!bg-transparent !border-none !shadow-none [&>button]:!bg-[#111119] [&>button]:!border [&>button]:!border-[rgba(255,255,255,0.06)] [&>button]:!text-[#8b8b9e] [&>button]:!rounded-md [&>button]:!w-7 [&>button]:!h-7" />
      </ReactFlow>
    </div>
  );
}
