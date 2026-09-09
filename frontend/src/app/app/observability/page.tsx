"use client";

import { useMetrics } from "@/lib/hooks";
import { TelemetryView } from "@/components/TelemetryView";

export default function ObservabilityPage() {
  const { metrics } = useMetrics(5000);

  return (
    <div className="p-4 sm:p-6 max-w-7xl w-full mx-auto space-y-4">
      <div>
        <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Observability &amp; Telemetry
        </h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
          Real-time metrics for latency, token consumption, grounding score distributions, and self-healing events.
        </p>
      </div>

      <div className="rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 shadow-xs bg-white dark:bg-slate-900">
        <TelemetryView metricsSnapshot={metrics} />
      </div>
    </div>
  );
}
