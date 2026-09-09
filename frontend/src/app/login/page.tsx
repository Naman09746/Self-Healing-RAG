"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Brain,
  Mail,
  Lock,
  Eye,
  EyeOff,
  ArrowRight,
  Loader2,
  ShieldCheck,
  AlertCircle,
} from "lucide-react";
import { auth, setTokens } from "@/lib/api";
import { useToast } from "@/components/Toast";
import ThemeToggle from "@/components/ThemeToggle";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const redirectUrl = searchParams.get("redirect") || "/app/dashboard";
  const isDev = process.env.NODE_ENV !== "production";

  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("rag_access_token") : null;
    if (token) {
      router.replace(redirectUrl);
    }
  }, [router, redirectUrl]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError("Please provide both email and password.");
      return;
    }

    setError(null);
    setLoading(true);

    try {
      const result = await auth.login(email.trim(), password);
      setTokens(result.access_token, result.refresh_token);
      toast.success("Signed in successfully. Welcome back!");
      router.replace(redirectUrl);
    } catch (err) {
      const msg = (err as Error).message || "Authentication failed. Please verify your credentials.";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleDevFill = () => {
    setEmail("admin@self-healing-rag.local");
    setPassword("Admin12345!");
    setError(null);
  };

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 selection:bg-blue-100">
      {/* Left: Enterprise Brand Statement Panel */}
      <div className="hidden lg:flex w-1/2 relative overflow-hidden bg-gradient-to-br from-blue-900 via-indigo-950 to-slate-950 text-white p-12 flex-col justify-between">
        <div className="relative z-10 flex items-center justify-between">
          <Link href="/" className="inline-flex items-center gap-2.5 group">
            <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center shadow-md shadow-blue-500/20 group-hover:scale-105 transition-transform">
              <Brain size={18} className="text-white" />
            </div>
            <div>
              <div className="text-sm font-bold tracking-tight">Nexus Core</div>
              <div className="text-[10px] text-blue-300 font-mono">Self-Healing RAG</div>
            </div>
          </Link>
        </div>

        <div className="relative z-10 max-w-md my-auto space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-400/20 text-blue-300 text-xs font-semibold">
            <ShieldCheck size={14} className="text-blue-400" />
            <span>Multi-Agent Hallucination Firewall</span>
          </div>

          <h1 className="text-3xl font-extrabold tracking-tight text-white leading-tight">
            Knowledge That Heals Itself. Answers You Can Trust.
          </h1>

          <p className="text-xs text-slate-300 leading-relaxed">
            Enterprise-grade multi-agent retrieval pipeline. Every answer is decomposed into atomic claims, grounded against hybrid memory, and healed in real-time.
          </p>

          <div className="pt-4 border-t border-white/10 grid grid-cols-2 gap-4 text-xs font-mono text-slate-300">
            <div>
              <div className="text-white font-bold text-base">99.1%</div>
              <div className="text-slate-400 text-[11px]">Self-Healing Resolution</div>
            </div>
            <div>
              <div className="text-white font-bold text-base">&lt; 250ms</div>
              <div className="text-slate-400 text-[11px]">P95 Retrieval Latency</div>
            </div>
          </div>
        </div>

        <div className="relative z-10 text-[11px] text-slate-400">
          Nexus Core v2.4 Enterprise &bull; SOC-2 & HIPAA compliant architecture
        </div>
      </div>

      {/* Right: Authentication Form */}
      <div className="flex-1 flex flex-col justify-between p-6 sm:p-12 lg:p-16">
        <div className="flex items-center justify-between">
          <Link href="/" className="lg:hidden inline-flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white">
              <Brain size={16} />
            </div>
            <span className="font-bold text-xs">Nexus Core</span>
          </Link>
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </div>

        <div className="max-w-md w-full mx-auto my-auto py-8">
          <div className="mb-6">
            <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              Sign In to Nexus Core
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Enter your credentials to access your multi-agent RAG workspaces.
            </p>
          </div>

          {error && (
            <div className="mb-5 p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 text-xs flex items-start gap-2.5">
              <AlertCircle size={15} className="shrink-0 mt-0.5 text-rose-600 dark:text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Work Email
              </label>
              <div className="relative">
                <Mail size={14} className="absolute left-3 top-3 text-slate-400" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  required
                  autoFocus
                  className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 transition-all placeholder:text-slate-400"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Password
                </label>
              </div>
              <div className="relative">
                <Lock size={14} className="absolute left-3 top-3 text-slate-400" />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  required
                  className="w-full pl-9 pr-10 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 transition-all placeholder:text-slate-400"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs">
              <label className="flex items-center gap-2 cursor-pointer text-slate-600 dark:text-slate-400">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                />
                <span>Remember me</span>
              </label>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold text-xs flex items-center justify-center gap-2 shadow-xs transition-colors cursor-pointer"
            >
              {loading ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  <span>Authenticating...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight size={13} />
                </>
              )}
            </button>
          </form>

          {/* Development / Demo fill button ONLY in development (User Req #4) */}
          {isDev && (
            <div className="mt-4 pt-4 border-t border-dashed border-slate-200 dark:border-slate-800 text-center">
              <button
                type="button"
                onClick={handleDevFill}
                className="text-[11px] font-mono text-blue-600 hover:underline inline-flex items-center gap-1"
              >
                <span>[Dev Mode] Quick-fill Admin Credentials</span>
              </button>
            </div>
          )}

          <div className="mt-6 text-center text-xs text-slate-500 dark:text-slate-400">
            Don&apos;t have an account?{" "}
            <Link
              href={`/signup${searchParams.get("redirect") ? `?redirect=${encodeURIComponent(searchParams.get("redirect")!)}` : ""}`}
              className="font-semibold text-blue-600 hover:underline"
            >
              Create an account
            </Link>
          </div>
        </div>

        <div className="text-center text-[11px] text-slate-400">
          &copy; {new Date().getFullYear()} Nexus Core. Enterprise-grade AI systems.
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 text-xs text-slate-500">
          Loading login...
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
