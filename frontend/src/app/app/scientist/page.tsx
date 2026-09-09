"use client";

import { AESStudio } from "@/components/AESStudio";

export default function ScientistPage() {
  return (
    <div className="p-4 sm:p-6 max-w-7xl w-full mx-auto space-y-4">
      <div>
        <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Autonomous Experiment Scientist (AES) Studio
        </h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
          Bayesian multi-objective hyperparameter optimization for RAG quality, Pareto efficiency, and latency reduction.
        </p>
      </div>

      <div className="rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 shadow-xs bg-white dark:bg-slate-900">
        <AESStudio />
      </div>
    </div>
  );
}
