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
  chroma: "ChromaDB",
  redis: "Redis",
  postgres: "PostgreSQL",
  neo4j: "Neo4j",
  ollama: "Ollama",
};

export default function SystemStatus() {
  const [services, setServices] = useState<Service[]>([
    { id: "chroma", label: "ChromaDB", status: "unknown", latency: 0 },
    { id: "redis", label: "Redis", status: "unknown", latency: 0 },
    { id: "postgres", label: "PostgreSQL", status: "unknown", latency: 0 },
    { id: "neo4j", label: "Neo4j", status: "unknown", latency: 0 },
    { id: "ollama", label: "Ollama", status: "unknown", latency: 0 },
  ]);
  const [loading, setLoading] = useState(true);

  const checkHealth = useCallback(async () => {
    try {
      const data = await health.check();
      if (data && data.services) {
        const parsed: Service[] = Object.entries(data.services).map(([key, val]) => {
          const label = SERVICE_LABELS[key] || key.toUpperCase();
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
