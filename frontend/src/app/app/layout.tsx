"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/hooks";
import AppShell from "@/components/layout/AppShell";
import { Loader2, Brain } from "lucide-react";

export default function AppProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { authenticated, loading } = useAuth();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!loading && mounted) {
      if (!authenticated) {
        const fullPath =
          typeof window !== "undefined"
            ? window.location.pathname + window.location.search
            : pathname;
        router.replace(`/login?redirect=${encodeURIComponent(fullPath)}`);
      }
    }
  }, [authenticated, loading, mounted, pathname, router]);

  // Loading state during auth initialization
  if (loading || !mounted || !authenticated) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
        <div className="flex flex-col items-center gap-4 text-center p-6">
          <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20 animate-pulse">
            <Brain size={22} />
          </div>
          <div className="space-y-1">
            <h2 className="text-sm font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              Verifying Nexus Session
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Authenticating against multi-agent RAG cluster...
            </p>
          </div>
          <Loader2 size={18} className="animate-spin text-blue-600 mt-2" />
        </div>
      </div>
    );
  }

  return <AppShell>{children}</AppShell>;
}
