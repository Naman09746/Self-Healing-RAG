"use client";

import { EvaluationSuite } from "@/components/EvaluationSuite";

export default function BenchmarksPage() {
  return (
    <div className="p-4 sm:p-6 max-w-7xl w-full mx-auto space-y-4">
      <div>
        <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Evaluation &amp; Benchmarks
        </h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
          RAGAS evaluation suite for measuring faithfulness, answer relevancy, and context retrieval recall against golden benchmarks.
        </p>
      </div>

      <div className="rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 shadow-xs bg-white dark:bg-slate-900">
        <EvaluationSuite />
      </div>
    </div>
  );
}
