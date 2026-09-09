"use client";

import Link from "next/link";
import { Brain, ArrowLeft, LayoutDashboard, Home } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 p-6 text-center">
      <div className="max-w-md w-full space-y-6">
        <div className="w-12 h-12 rounded-2xl bg-blue-600 flex items-center justify-center text-white mx-auto shadow-lg shadow-blue-500/20">
          <Brain size={24} />
        </div>

        <div className="space-y-2">
          <span className="text-xs font-mono font-semibold text-blue-600 uppercase tracking-wider bg-blue-50 dark:bg-blue-950/50 px-2.5 py-1 rounded-full border border-blue-200 dark:border-blue-800">
            Error 404 &bull; Page Not Found
          </span>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Node Not In Graph
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed max-w-sm mx-auto">
            The route or resource you are attempting to access does not exist in Nexus Core or has been relocated to a dedicated workspace.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <Link
            href="/app/dashboard"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs transition-colors shadow-xs"
          >
            <LayoutDashboard size={14} />
            <span>Open App Dashboard</span>
          </Link>

          <Link
            href="/"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-white dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-800 font-semibold text-xs transition-colors"
          >
            <Home size={14} />
            <span>Return to Homepage</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
