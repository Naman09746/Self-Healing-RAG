"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Brain,
  Mail,
  Lock,
  Eye,
  EyeOff,
  ArrowRight,
  Loader2,
  CheckCircle,
  AlertCircle,
  Sparkles,
  GitBranch,
  MessageSquare,
} from "lucide-react";
import { auth, setTokens } from "@/lib/api";

export default function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    // Check if already authenticated
    const token = localStorage.getItem("rag_access_token");
    if (token) {
      router.push("/dashboard");
    }
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (mode === "login") {
        const result = await auth.login(email, password);
        setTokens(result.access_token, result.refresh_token);
        setSuccess(true);
        setTimeout(() => router.push("/dashboard"), 500);
      } else {
        const result = await auth.signup(email, password, name);
        setTokens(result.access_token, result.refresh_token);
        setSuccess(true);
        setTimeout(() => router.push("/dashboard"), 500);
      }
    } catch (err) {
      setError((err as Error).message || "Authentication failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex" style={{ background: "#08080c" }}>
      {/* Left — Brand */}
      <div className="hidden lg:flex w-1/2 relative overflow-hidden items-center justify-center">
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 60% 50% at 30% 50%, rgba(99,102,241,0.1) 0%, transparent 70%), radial-gradient(ellipse 40% 40% at 70% 80%, rgba(139,92,246,0.06) 0%, transparent 60%)",
          }}
        />
        <div className="relative z-10 text-center max-w-md">
          <div
            className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-6"
            style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}
          >
            <Brain size={32} className="text-white" />
          </div>
          <h1 className="text-3xl font-bold mb-3" style={{ color: "#e8e8ed" }}>
            Nexus Core
          </h1>
          <p className="text-sm leading-relaxed" style={{ color: "#8b8b9e" }}>
            Enterprise-grade self-healing RAG platform.
            <br />
            Verified answers from your knowledge base.
          </p>
          <div className="mt-8 space-y-3 text-left max-w-xs mx-auto">
            {[
              "Multi-agent pipeline with self-healing",
              "Real-time hallucination detection",
              "Enterprise-grade security & RBAC",
            ].map((item) => (
              <div key={item} className="flex items-center gap-3 text-sm" style={{ color: "#8b8b9e" }}>
                <CheckCircle size={14} style={{ color: "#22c55e" }} />
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right — Form */}
      <div className="flex-1 flex items-center justify-center p-5">
        <div className="w-full max-w-sm">
          {/* Logo (mobile) */}
          <div className="lg:hidden flex items-center gap-2.5 mb-8 justify-center">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}
            >
              <Brain size={16} className="text-white" />
            </div>
            <span className="text-sm font-semibold" style={{ color: "#e8e8ed" }}>
              Nexus Core
            </span>
          </div>

          <div className="text-center mb-8">
            <h2 className="text-xl font-bold mb-1" style={{ color: "#e8e8ed" }}>
              {mode === "login" ? "Welcome back" : "Create account"}
            </h2>
            <p className="text-xs" style={{ color: "#525266" }}>
              {mode === "login"
                ? "Sign in to access your knowledge base"
                : "Start with a free account"}
            </p>
          </div>

          {error && (
            <div className="alert alert-error mb-4">
              <AlertCircle size={14} />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="alert mb-4" style={{ background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.18)", color: "#22c55e", borderRadius: "10px", padding: "10px 14px", fontSize: "12px" }}>
              <CheckCircle size={14} />
              <span>Authentication successful! Redirecting...</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "signup" && (
              <div>
                <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block" style={{ color: "#525266" }}>
                  Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="input text-xs"
                  placeholder="Your name"
                  required
                />
              </div>
            )}

            <div>
              <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block" style={{ color: "#525266" }}>
                Email
              </label>
              <div className="input-icon">
                <Mail size={13} className="icon" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input text-xs pl-9"
                  placeholder="you@company.com"
                  required
                />
              </div>
            </div>

            <div>
              <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block" style={{ color: "#525266" }}>
                Password
              </label>
              <div className="relative">
                <Lock size={13} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "#525266" }} />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input text-xs pl-9 pr-9"
                  placeholder="••••••••"
                  required
                  minLength={8}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2"
                  style={{ color: "#525266" }}
                >
                  {showPassword ? <EyeOff size={13} /> : <Eye size={13} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || success}
              className="btn btn-primary w-full justify-center text-sm py-2.5"
            >
              {loading ? (
                <>
                  <Loader2 size={14} className="animate-spin" /> Signing in...
                </>
              ) : (
                <>
                  {mode === "login" ? "Sign In" : "Create Account"}{" "}
                  <ArrowRight size={14} />
                </>
              )}
            </button>
          </form>

          <div className="mt-6">
            <div className="relative mb-4">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }} />
              </div>
              <div className="relative flex justify-center text-[10px]" style={{ color: "#525266" }}>
                <span className="px-2" style={{ background: "#08080c" }}>or continue with</span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <button className="btn btn-outline text-xs justify-center py-2">
                <GitBranch size={13} /> GitHub
              </button>
              <button className="btn btn-outline text-xs justify-center py-2">
                <MessageSquare size={13} /> SSO
              </button>
            </div>
          </div>

          <p className="text-center mt-6 text-xs" style={{ color: "#525266" }}>
            {mode === "login" ? "Don't have an account? " : "Already have an account? "}
            <button
              onClick={() => {
                setMode(mode === "login" ? "signup" : "login");
                setError(null);
              }}
              className="font-medium hover:text-indigo-400 transition-colors"
              style={{ color: "#a5b4fc" }}
            >
              {mode === "login" ? "Sign up" : "Sign in"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
