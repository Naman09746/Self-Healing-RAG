"use client";

import { useState, useEffect, useCallback } from "react";
import { Activity } from "lucide-react";
import { health } from "@/lib/api";

interface Service {
  id: string;
  label: string;
  status: "healthy" | "degraded" | "down" | "unknown";
  latency: number;
}

const SERVICE_LABELS: Record<string, string> = {
  vector_store: "Vector Store",
  session_store: "Session Store",
  sparse_store: "Sparse Index",
  reranker: "Reranker",
  graph_store: "Graph Store",
  postgres: "PostgreSQL",
  ollama: "LLM Inference",
  redis: "Redis",
  neo4j: "Neo4j",
};

export default function SystemStatus() {
  const [services, setServices] = useState<Service[]>([
    { id: "vector_store", label: "Vector (pgvector)", status: "healthy", latency: 0 },
    { id: "sparse_store", label: "Sparse (tsvector)", status: "healthy", latency: 0 },
    { id: "postgres", label: "PostgreSQL", status: "healthy", latency: 0 },
    { id: "reranker", label: "Reranker (RRF)", status: "healthy", latency: 0 },
  ]);
  const [loading, setLoading] = useState(true);

  const checkHealth = useCallback(async () => {
    try {
      const data = await health.check();
      if (data && data.services) {
        const parsed: Service[] = Object.entries(data.services)
          .filter(([key, val]: [string, any]) => {
            // Hide legacy services marked as not_used
            if (val && typeof val === "object" && val.status === "not_used") return false;
            // Filter out duplicate legacy aliases if vector_store is present
            if (["chroma", "redis", "neo4j"].includes(key) && data.services.vector_store) return false;
            return true;
          })
          .map(([key, val]) => {
            const providerTag = typeof val === "object" && (val as any).provider ? ` (${(val as any).provider})` : "";
            const baseLabel = SERVICE_LABELS[key] || key.toUpperCase();
            const label = `${baseLabel}${providerTag}`;
            let status: "healthy" | "degraded" | "down" | "unknown" = "unknown";
            let latency = 0;

            if (typeof val === "object" && val !== null) {
              const rawStatus = (val as any).status;
              if (rawStatus === "healthy") status = "healthy";
              else if (rawStatus === "unhealthy") status = "down";
              else if (rawStatus === "degraded" || rawStatus === "disabled_or_unavailable") status = "degraded";
              latency = (val as any).latency_ms || 0;
            } else if (typeof val === "string") {
              status = "healthy";
            }

            return { id: key, label, status, latency };
          });

        if (parsed.length > 0) {
          setServices(parsed);
        }
      }
    } catch {
      setServices([{ id: "api", label: "API", status: "down", latency: 0 }]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  return (
    <div className="flex items-center gap-2">
      {services.map((svc) => (
        <div
          key={svc.id}
          className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium border transition-all ${
            svc.status === "healthy"
              ? "bg-emerald-50 text-emerald-700 border-emerald-200/80"
              : svc.status === "degraded"
              ? "bg-amber-50 text-amber-700 border-amber-200/80"
              : svc.status === "down"
              ? "bg-rose-50 text-rose-700 border-rose-200/80"
              : "bg-slate-100 text-slate-600 border-slate-200"
          }`}
          style={{ opacity: loading ? 0.6 : 1 }}
          title={`${svc.label}: ${svc.status}${svc.latency ? ` (${svc.latency}ms)` : ""}`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full shrink-0 ${
              svc.status === "healthy"
                ? "bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.6)]"
                : svc.status === "degraded"
                ? "bg-amber-500 shadow-[0_0_6px_rgba(245,158,11,0.6)]"
                : svc.status === "down"
                ? "bg-rose-500"
                : "bg-slate-400"
            }`}
          />
          <span>{svc.label}</span>
        </div>
      ))}
    </div>
  );
}
