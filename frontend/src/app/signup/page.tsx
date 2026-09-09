"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Brain,
  Mail,
  Lock,
  User,
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

function SignupForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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
      setError("Please provide all required fields.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setError(null);
    setLoading(true);

    try {
      const result = await auth.signup(email.trim(), password, name.trim());
      setTokens(result.access_token, result.refresh_token);
      toast.success("Account created successfully. Welcome to Nexus Core!");
      router.replace(redirectUrl);
    } catch (err) {
      const msg = (err as Error).message || "Registration failed. Please try again.";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleDevFill = () => {
    setName("Production Engineer");
    setEmail(`operator_${Math.floor(Math.random() * 1000)}@self-healing-rag.local`);
    setPassword("Operator12345!");
    setConfirmPassword("Operator12345!");
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
            <span>Multi-Agent Architecture</span>
          </div>

          <h1 className="text-3xl font-extrabold tracking-tight text-white leading-tight">
            Provision Your Self-Healing Knowledge Workspace
          </h1>

          <p className="text-xs text-slate-300 leading-relaxed">
            Deploy autonomous agents to safeguard your company&apos;s knowledge base. Hybrid vector + graph search, real-time hallucination detection, and automatic query rewriting out of the box.
          </p>

          <div className="pt-4 border-t border-white/10 space-y-2 text-xs text-slate-300">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span>Full tenant isolation &amp; RBAC enforcement</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span>Live LangGraph execution visualization</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span>Autonomous Experiment Scientist (AES) optimization</span>
            </div>
          </div>
        </div>

        <div className="relative z-10 text-[11px] text-slate-400">
          Nexus Core v2.4 Enterprise &bull; Secure production deployment
        </div>
      </div>

      {/* Right: Signup Form */}
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
              Create an Account
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Start building verified, hallucination-free knowledge pipelines.
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
                Full Name
              </label>
              <div className="relative">
                <User size={14} className="absolute left-3 top-3 text-slate-400" />
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Jane Doe"
                  className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 transition-all placeholder:text-slate-400"
                />
              </div>
            </div>

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
                  className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 transition-all placeholder:text-slate-400"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock size={14} className="absolute left-3 top-3 text-slate-400" />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimum 8 characters"
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

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Confirm Password
              </label>
              <div className="relative">
                <Lock size={14} className="absolute left-3 top-3 text-slate-400" />
                <input
                  type={showPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter password"
                  required
                  className="w-full pl-9 pr-10 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 transition-all placeholder:text-slate-400"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold text-xs flex items-center justify-center gap-2 shadow-xs transition-colors cursor-pointer mt-2"
            >
              {loading ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  <span>Creating Account...</span>
                </>
              ) : (
                <>
                  <span>Create Account</span>
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
                <span>[Dev Mode] Quick-fill Random Operator</span>
              </button>
            </div>
          )}

          <div className="mt-6 text-center text-xs text-slate-500 dark:text-slate-400">
            Already have an account?{" "}
            <Link
              href={`/login${searchParams.get("redirect") ? `?redirect=${encodeURIComponent(searchParams.get("redirect")!)}` : ""}`}
              className="font-semibold text-blue-600 hover:underline"
            >
              Sign in
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

export default function SignupPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 text-xs text-slate-500">
          Loading registration...
        </div>
      }
    >
      <SignupForm />
    </Suspense>
  );
}
