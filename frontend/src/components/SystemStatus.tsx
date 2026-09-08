"use client";

import { useState, useEffect, useCallback } from "react";
import { Activity } from "lucide-react";

interface Service {
  id: string;
  label: string;
  status: "healthy" | "degraded" | "down" | "unknown";
  latency: number;
}

export default function SystemStatus() {
  const [services, setServices] = useState<Service[]>([
    { id: "api", label: "API", status: "unknown", latency: 0 },
  ]);
  const [loading, setLoading] = useState(true);

  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch("http://localhost:8000/health", { signal: AbortSignal.timeout(5000) });
      if (res.ok) {
        setServices([{ id: "api", label: "API", status: "healthy", latency: 0 }]);
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
