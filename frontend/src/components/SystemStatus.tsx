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
    <div className="flex items-center gap-2.5">
      {services.map((svc) => (
        <div
          key={svc.id}
          className="flex items-center gap-1.5 px-2 py-1 rounded-md transition-all"
          style={{
            background: svc.status === "healthy" ? "rgba(34,197,94,0.06)" : svc.status === "degraded" ? "rgba(245,158,11,0.06)" : svc.status === "down" ? "rgba(239,68,68,0.06)" : "rgba(255,255,255,0.03)",
            opacity: loading ? 0.5 : 1,
          }}
          title={`${svc.label}: ${svc.status}${svc.latency ? ` (${svc.latency}ms)` : ""}`}
        >
          <span
            className="w-1.5 h-1.5 rounded-full shrink-0"
            style={{
              background: svc.status === "healthy" ? "#22c55e" : svc.status === "degraded" ? "#f59e0b" : svc.status === "down" ? "#ef4444" : "#525266",
              boxShadow: svc.status === "healthy" ? "0 0 4px rgba(34,197,94,0.5)" : "none",
            }}
          />
          <span className="text-[10px] font-medium" style={{ color: "var(--text-secondary)" }}>
            {svc.label}
          </span>
        </div>
      ))}
    </div>
  );
}
