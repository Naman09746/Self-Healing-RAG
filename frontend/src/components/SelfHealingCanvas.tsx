"use client";

import React, { useRef, useEffect, useState, useCallback } from "react";
import { Sparkles, RefreshCw, ShieldCheck, Zap } from "lucide-react";

interface Node {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  baseRadius: number;
  label: string;
  type: "document" | "vector" | "critic" | "grounding" | "healer";
  pulse: number;
}

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  alpha: number;
  color: string;
  size: number;
}

export default function SelfHealingCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isHealing, setIsHealing] = useState(false);
  const [healingCount, setHealingCount] = useState(1);
  const [hudStatus, setHudStatus] = useState("Lattice Harmonic & Grounded");
  const [hudGrounding, setHudGrounding] = useState(98.8);
  const mouseRef = useRef<{ x: number; y: number; active: boolean }>({
    x: -1000,
    y: -1000,
    active: false,
  });

  const triggerHealSimulation = useCallback(() => {
    if (isHealing) return;
    setIsHealing(true);
    setHudStatus("Hallucination Detected &bull; Rewriting Query...");
    setHudGrounding(54.2);

    setTimeout(() => {
      setHudStatus("Critic Entailment Verified &bull; Grounding Restored");
      setHudGrounding(99.4);
      setHealingCount((c) => c + 1);
      setTimeout(() => {
        setIsHealing(false);
        setHudStatus("Lattice Harmonic & Grounded");
      }, 1400);
    }, 1200);
  }, [isHealing]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || 800);
    let height = (canvas.height = canvas.parentElement?.clientHeight || 460);

    const handleResize = () => {
      if (!canvas || !canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = canvas.parentElement.clientHeight;
    };
    window.addEventListener("resize", handleResize);

    // Generate Nodes
    const NODE_COUNT = 32;
    const LABELS = ["ChromaDB", "Neo4j", "BM25", "Critic", "LLM", "Healer", "Grounding", "Chunk", "Embedding", "RRF", "Claim"];
    const nodes: Node[] = [];

    for (let i = 0; i < NODE_COUNT; i++) {
      const type: Node["type"] =
        i === 0 ? "healer" : i === 1 ? "critic" : i % 3 === 0 ? "vector" : "document";
      nodes.push({
        x: Math.random() * (width - 80) + 40,
        y: Math.random() * (height - 80) + 40,
        vx: (Math.random() - 0.5) * 0.7,
        vy: (Math.random() - 0.5) * 0.7,
        radius: type === "healer" ? 6 : type === "critic" ? 5 : 3.5,
        baseRadius: type === "healer" ? 6 : type === "critic" ? 5 : 3.5,
        label: LABELS[i % LABELS.length],
        type,
        pulse: Math.random() * Math.PI * 2,
      });
    }

    const particles: Particle[] = [];

    // Animation Loop
    let time = 0;
    const render = () => {
      time += 0.02;
      ctx.clearRect(0, 0, width, height);

      // Check theme
      const isDark = document.documentElement.classList.contains("dark");
      const baseLineColor = isDark ? "rgba(99, 102, 241, " : "rgba(37, 99, 235, ";
      const nodeFill = isDark ? "#60a5fa" : "#2563eb";

      // 1. Draw Connecting Lines
      const MAX_DIST = 130;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < MAX_DIST) {
            const alpha = (1 - dist / MAX_DIST) * (isDark ? 0.22 : 0.16);
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.strokeStyle = `${baseLineColor}${alpha})`;
            ctx.lineWidth = isHealing && (nodes[i].type === "healer" || nodes[j].type === "healer") ? 1.5 : 0.75;
            ctx.stroke();
          }
        }
      }

      // 2. Mouse Interaction Connections
      if (mouseRef.current.active) {
        const mx = mouseRef.current.x;
        const my = mouseRef.current.y;
        for (let i = 0; i < nodes.length; i++) {
          const dx = nodes[i].x - mx;
          const dy = nodes[i].y - my;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 150) {
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(mx, my);
            ctx.strokeStyle = isDark ? `rgba(147, 197, 253, ${0.35 * (1 - dist / 150)})` : `rgba(37, 99, 235, ${0.3 * (1 - dist / 150)})`;
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        }
      }

      // 3. Healing Beam & Burst Pulse Effect
      if (isHealing) {
        const healer = nodes[0]; // first node is designated healer
        const target = nodes[1]; // critic node

        // Pulsating scanning wave
        ctx.save();
        ctx.beginPath();
        const pulseR = 40 + Math.sin(time * 8) * 20;
        ctx.arc(healer.x, healer.y, pulseR, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(16, 185, 129, 0.4)";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 4]);
        ctx.stroke();
        ctx.restore();

        // High-energy laser connection
        ctx.beginPath();
        ctx.moveTo(healer.x, healer.y);
        ctx.lineTo(target.x, target.y);
        ctx.strokeStyle = "rgba(16, 185, 129, 0.85)";
        ctx.lineWidth = 2.5;
        ctx.shadowColor = "#10b981";
        ctx.shadowBlur = 12;
        ctx.stroke();
        ctx.shadowBlur = 0;

        // Spawn burst particles around target
        if (Math.random() < 0.6) {
          particles.push({
            x: target.x,
            y: target.y,
            vx: (Math.random() - 0.5) * 4,
            vy: (Math.random() - 0.5) * 4,
            alpha: 1,
            color: Math.random() > 0.5 ? "#10b981" : "#3b82f6",
            size: Math.random() * 3 + 1,
          });
        }
      }

      // 4. Update & Render Particles
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.alpha -= 0.025;
        if (p.alpha <= 0) {
          particles.splice(i, 1);
          continue;
        }
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = p.alpha;
        ctx.fill();
        ctx.globalAlpha = 1;
      }

      // 5. Update & Draw Nodes
      for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i];

        // Move nodes
        node.x += node.vx;
        node.y += node.vy;

        // Bounce on boundaries
        if (node.x < 20 || node.x > width - 20) node.vx *= -1;
        if (node.y < 20 || node.y > height - 20) node.vy *= -1;

        // Mouse gentle repel/attract
        if (mouseRef.current.active) {
          const mdx = mouseRef.current.x - node.x;
          const mdy = mouseRef.current.y - node.y;
          const mdist = Math.sqrt(mdx * mdx + mdy * mdy);
          if (mdist < 100 && mdist > 5) {
            node.x -= (mdx / mdist) * 0.4;
            node.y -= (mdy / mdist) * 0.4;
          }
        }

        // Draw node
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
        if (node.type === "healer") {
          ctx.fillStyle = isHealing ? "#10b981" : "#2563eb";
          ctx.shadowColor = isHealing ? "#10b981" : "#2563eb";
          ctx.shadowBlur = 8;
        } else if (node.type === "critic") {
          ctx.fillStyle = isHealing ? "#f59e0b" : "#6366f1";
          ctx.shadowBlur = 0;
        } else {
          ctx.fillStyle = nodeFill;
          ctx.shadowBlur = 0;
        }
        ctx.fill();
        ctx.shadowBlur = 0;

        // Subtle labels on prominent nodes
        if (node.type === "healer" || node.type === "critic" || i % 4 === 0) {
          ctx.font = "9px var(--font-mono, monospace)";
          ctx.fillStyle = isDark ? "rgba(226, 232, 240, 0.75)" : "rgba(71, 85, 105, 0.85)";
          ctx.fillText(node.label, node.x + 8, node.y + 3);
        }
      }

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", handleResize);
    };
  }, [isHealing]);

  return (
    <div className="relative w-full h-[380px] sm:h-[440px] rounded-2xl bg-white/80 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-xl overflow-hidden group">
      {/* 1. Interactive Canvas */}
      <canvas
        ref={canvasRef}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          mouseRef.current = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top,
            active: true,
          };
        }}
        onMouseLeave={() => {
          mouseRef.current.active = false;
        }}
        className="w-full h-full cursor-crosshair block"
      />

      {/* 2. Top HUD Bar */}
      <div className="absolute top-3 left-3 right-3 flex items-center justify-between pointer-events-none">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border border-slate-200 dark:border-slate-800 shadow-xs text-xs">
          <span
            className={`w-2 h-2 rounded-full ${
              isHealing ? "bg-amber-500 animate-ping" : "bg-emerald-500"
            }`}
          />
          <span
            className="font-medium text-slate-800 dark:text-slate-200"
            dangerouslySetInnerHTML={{ __html: hudStatus }}
          />
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border border-slate-200 dark:border-slate-800 shadow-xs text-xs font-mono text-slate-700 dark:text-slate-300">
          <span>Grounding:</span>
          <span
            className={`font-bold ${
              hudGrounding > 80
                ? "text-emerald-600 dark:text-emerald-400"
                : "text-amber-600 dark:text-amber-400"
            }`}
          >
            {hudGrounding.toFixed(1)}%
          </span>
        </div>
      </div>

      {/* 3. Bottom Interactive Trigger Bar */}
      <div className="absolute bottom-3 left-3 right-3 flex flex-col sm:flex-row items-center justify-between gap-2 p-2.5 rounded-xl bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border border-slate-200 dark:border-slate-800 shadow-xs text-xs">
        <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 text-[11px] px-2">
          <Zap size={12} className="text-blue-600" />
          <span>Interactive Lattice &bull; Move mouse to deform filaments</span>
        </div>

        <button
          type="button"
          onClick={triggerHealSimulation}
          disabled={isHealing}
          className="w-full sm:w-auto inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold text-xs shadow-xs transition-colors cursor-pointer"
        >
          <RefreshCw size={12} className={isHealing ? "animate-spin" : ""} />
          <span>{isHealing ? "Self-Healing in Progress..." : "Trigger Self-Healing Anomaly"}</span>
        </button>
      </div>
    </div>
  );
}
