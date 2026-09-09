"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import SelfHealingCanvas from "@/components/SelfHealingCanvas";
import { useAuth } from "@/lib/hooks";
import {
  ArrowRight,
  Brain,
  Globe,
  Shield,
  Zap,
  Layers,
  CheckCircle,
  AlertTriangle,
  Cpu,
  BarChart3,
  GitBranch,
  Search,
  BookOpen,
  Sparkles,
  Menu,
  X,
  FileText,
  Workflow,
  CheckCircle2,
  RefreshCw,
  Clock,
  ShieldCheck,
  ChevronDown,
  Play,
  Database,
  Lock,
} from "lucide-react";

/* ─── Static Brand Logos / Tech Stack ────────────────── */
const TECH_PARTNERS = [
  "PostgreSQL / Neon",
  "ChromaDB",
  "LangGraph",
  "FastAPI",
  "Groq Cloud",
  "Redis / Upstash",
  "Neo4j Graph",
  "Docker",
];

export default function LandingPage() {
  const { authenticated } = useAuth();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const appDestination = authenticated ? "/app/dashboard" : "/login";
  const signupDestination = authenticated ? "/app/dashboard" : "/signup";

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 selection:bg-blue-100 dark:selection:bg-blue-950">
      {/* ════════════════════════════════════════════════════
         1. FIXED HEADER NAVIGATION
         ════════════════════════════════════════════════════ */}
      <header
        className={`fixed top-0 left-0 right-0 z-50 h-16 transition-all duration-200 ${
          scrolled
            ? "bg-white/85 dark:bg-slate-950/85 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 shadow-xs"
            : "bg-white/60 dark:bg-slate-950/60 backdrop-blur-xs border-b border-transparent"
        }`}
      >
        <div className="max-w-7xl mx-auto h-full px-4 sm:px-6 flex items-center justify-between">
          {/* Brand */}
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-xs shadow-blue-500/20 group-hover:scale-105 transition-transform">
              <Brain size={16} />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold tracking-tight text-slate-900 dark:text-slate-100">
                Nexus Core
              </span>
              <span className="hidden sm:inline text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
                v2.4 Production
              </span>
            </div>
          </Link>

          {/* Desktop Navigation Links */}
          <nav className="hidden md:flex items-center gap-1 text-xs font-medium text-slate-600 dark:text-slate-400">
            <a
              href="#features"
              className="px-3 py-1.5 rounded-md hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
            >
              Features
            </a>
            <a
              href="#how-it-works"
              className="px-3 py-1.5 rounded-md hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
            >
              How It Works
            </a>
            <a
              href="#pipeline"
              className="px-3 py-1.5 rounded-md hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
            >
              Pipeline
            </a>
            <a
              href="#metrics"
              className="px-3 py-1.5 rounded-md hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
            >
              Metrics
            </a>
            <a
              href="#pricing"
              className="px-3 py-1.5 rounded-md hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
            >
              Pricing
            </a>
            <Link
              href="/docs"
              className="px-3 py-1.5 rounded-md hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
            >
              Docs
            </Link>
          </nav>

          {/* Desktop Actions */}
          <div className="hidden md:flex items-center gap-2.5">
            <ThemeToggle />
            <Link
              href={appDestination}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs shadow-xs transition-colors"
            >
              <span>{authenticated ? "Open App" : "Launch App"}</span>
              <ArrowRight size={13} />
            </Link>
          </div>

          {/* Mobile Actions */}
          <div className="flex items-center gap-2 md:hidden">
            <ThemeToggle />
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="p-2 rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              aria-label="Toggle Navigation"
            >
              {mobileOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {mobileOpen && (
          <div className="md:hidden bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 p-4 space-y-2 text-xs font-medium">
            <a
              href="#features"
              onClick={() => setMobileOpen(false)}
              className="block p-2 rounded-md hover:bg-slate-50 dark:hover:bg-slate-800"
            >
              Features
            </a>
            <a
              href="#how-it-works"
              onClick={() => setMobileOpen(false)}
              className="block p-2 rounded-md hover:bg-slate-50 dark:hover:bg-slate-800"
            >
              How It Works
            </a>
            <a
              href="#pipeline"
              onClick={() => setMobileOpen(false)}
              className="block p-2 rounded-md hover:bg-slate-50 dark:hover:bg-slate-800"
            >
              Pipeline
            </a>
            <a
              href="#metrics"
              onClick={() => setMobileOpen(false)}
              className="block p-2 rounded-md hover:bg-slate-50 dark:hover:bg-slate-800"
            >
              Metrics
            </a>
            <a
              href="#pricing"
              onClick={() => setMobileOpen(false)}
              className="block p-2 rounded-md hover:bg-slate-50 dark:hover:bg-slate-800"
            >
              Pricing
            </a>
            <Link
              href="/docs"
              onClick={() => setMobileOpen(false)}
              className="block p-2 rounded-md hover:bg-slate-50 dark:hover:bg-slate-800"
            >
              Docs
            </Link>
            <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
              <Link
                href={appDestination}
                onClick={() => setMobileOpen(false)}
                className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg bg-blue-600 text-white font-semibold"
              >
                <span>{authenticated ? "Open Dashboard" : "Sign In to App"}</span>
                <ArrowRight size={13} />
              </Link>
            </div>
          </div>
        )}
      </header>

      {/* ════════════════════════════════════════════════════
         2. HERO SECTION
         ════════════════════════════════════════════════════ */}
      <section className="pt-28 pb-16 md:pt-36 md:pb-24 overflow-hidden relative border-b border-slate-200/80 dark:border-slate-800/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="max-w-3xl mx-auto text-center space-y-5">
            {/* Eyebrow */}
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300">
              <Sparkles size={13} className="text-blue-600 dark:text-blue-400" />
              <span>Self-Healing RAG &mdash; Now Available</span>
            </div>

            {/* Headline */}
            <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100 leading-[1.12]">
              Knowledge That Heals Itself. <br />
              <span className="bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-700 bg-clip-text text-transparent">
                Answers You Can Trust.
              </span>
            </h1>

            {/* Supporting Copy */}
            <p className="text-sm sm:text-base text-slate-600 dark:text-slate-400 max-w-2xl mx-auto leading-relaxed">
              Nexus Core is an enterprise-grade multi-agent RAG platform that detects hallucinations, self-corrects in real time, and delivers verified answers from your knowledge base.
            </p>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
              <Link
                href={signupDestination}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs sm:text-sm shadow-sm transition-all cursor-pointer"
              >
                <span>Get Started</span>
                <ArrowRight size={14} />
              </Link>
              <a
                href="#how-it-works"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-800 font-semibold text-xs sm:text-sm transition-colors"
              >
                <Play size={13} />
                <span>See How It Works</span>
              </a>
            </div>
          </div>

          {/* ── Extraordinary Interactive Self-Healing Visual Studio ───────── */}
          <div className="mt-12 sm:mt-16 max-w-5xl mx-auto space-y-6">
            {/* 1. Motion Neural Lattice Canvas */}
            <SelfHealingCanvas />

            {/* 2. Product Concept Architecture Preview */}
            <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl overflow-hidden">
              {/* macOS Chrome Header */}
            <div className="h-9 px-4 bg-slate-100/80 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-400" />
                <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
              </div>
              <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400 font-medium">
                nexus-core &bull; self-healing multi-agent pipeline
              </span>
              <div className="w-10" />
            </div>

            {/* Visual Step-by-Step Architecture Pipeline */}
            <div className="p-6 sm:p-8 bg-slate-50/50 dark:bg-slate-950/40 space-y-6">
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5 text-center">
                {[
                  { step: "1", title: "Query", sub: "User prompt", color: "border-blue-300 bg-blue-50/60 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300" },
                  { step: "2", title: "Retriever", sub: "Hybrid RRF", color: "border-slate-200 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300" },
                  { step: "3", title: "Reasoning", sub: "Multi-Agent", color: "border-slate-200 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300" },
                  { step: "4", title: "Grounding", sub: "Critic claim check", color: "border-emerald-300 bg-emerald-50/60 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300" },
                  { step: "5", title: "Critic Check", sub: "Threshold gate", color: "border-slate-200 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300" },
                  { step: "6", title: "Self-Heal", sub: "Rewrite loop", color: "border-amber-300 bg-amber-50/60 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300" },
                  { step: "7", title: "Output", sub: "Verified answer", color: "border-blue-600 bg-blue-600 text-white" },
                ].map((item, i) => (
                  <div
                    key={i}
                    className={`p-3 rounded-xl border text-xs font-medium flex flex-col justify-between ${item.color} shadow-2xs`}
                  >
                    <span className="text-[10px] font-mono opacity-70">Stage {item.step}</span>
                    <span className="font-bold my-1 truncate">{item.title}</span>
                    <span className="text-[10px] opacity-80 truncate">{item.sub}</span>
                  </div>
                ))}
              </div>

              {/* Verified Result Preview Card */}
              <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-left space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800 font-semibold">
                      <CheckCircle2 size={11} />
                      Verified Grounded (98.4%)
                    </span>
                    <span className="text-slate-400 font-mono text-[11px]">Latency: 242ms</span>
                  </div>
                  <span className="text-[11px] font-mono text-slate-400">Claims Verified: 4/4</span>
                </div>
                <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed font-sans">
                  &ldquo;When a low grounding score is detected, the Healer Agent rewrites the query, pulls fresh context via hybrid RRF search, and re-evaluates before outputting to the user.&rdquo;
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

      {/* ════════════════════════════════════════════════════
         3. TRUST / TECH STRIP
         ════════════════════════════════════════════════════ */}
      <div className="py-6 border-b border-slate-200/80 dark:border-slate-800/80 bg-white/50 dark:bg-slate-900/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <p className="text-[11px] font-mono uppercase tracking-wider text-slate-400 text-center mb-3">
            Engineered on Open Standards &bull; Production Infrastructure
          </p>
          <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
            {TECH_PARTNERS.map((tp, idx) => (
              <span key={idx} className="hover:text-slate-800 dark:hover:text-slate-200 transition-colors">
                {tp}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* ════════════════════════════════════════════════════
         4. CORE PROBLEM SECTION
         ════════════════════════════════════════════════════ */}
      <section className="py-16 md:py-20 border-b border-slate-200/80 dark:border-slate-800/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="max-w-2xl mx-auto text-center mb-12">
            <span className="text-xs font-mono font-semibold text-blue-600 uppercase tracking-wider">
              The Enterprise Challenge
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100 mt-1">
              Why Traditional RAG Fails in Production
            </h2>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-2">
              Flat vector search yields irrelevant chunks. LLMs hallucinate plausible-sounding falsehoods with no internal mechanism to self-correct.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-2.5">
              <div className="w-8 h-8 rounded-lg bg-rose-50 dark:bg-rose-950/50 text-rose-600 flex items-center justify-center">
                <AlertTriangle size={16} />
              </div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                Silent Hallucinations
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                Standard pipelines generate answers even when retrieved chunks lack evidence, delivering ungrounded hallucinations to users without warning.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-2.5">
              <div className="w-8 h-8 rounded-lg bg-amber-50 dark:bg-amber-950/50 text-amber-600 flex items-center justify-center">
                <RefreshCw size={16} />
              </div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                Zero Recovery Capability
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                When a query is ambiguous or poorly phrased, traditional systems run once and fail. There is no automated query re-planning or retry loop.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-2.5">
              <div className="w-8 h-8 rounded-lg bg-blue-50 dark:bg-blue-950/50 text-blue-600 flex items-center justify-center">
                <Database size={16} />
              </div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                Isolated Vector Search
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                Relying exclusively on dense embeddings misses exact keyword matches, structural graph relationships, and multi-hop entity context.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════
         5. HOW NEXUS CORE WORKS
         ════════════════════════════════════════════════════ */}
      <section id="how-it-works" className="scroll-mt-20 py-16 md:py-20 border-b border-slate-200/80 dark:border-slate-800/80 bg-white/40 dark:bg-slate-900/40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="max-w-2xl mx-auto text-center mb-12">
            <span className="text-xs font-mono font-semibold text-blue-600 uppercase tracking-wider">
              Verification Engine
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100 mt-1">
              How Nexus Core Solves Hallucinations
            </h2>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-2">
              A closed-loop verification architecture where independent agents inspect, score, and heal responses.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 max-w-5xl mx-auto">
            <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-2">
              <div className="text-xs font-mono font-bold text-blue-600">01 / Intake &amp; Plan</div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Adaptive Planning</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                Query complexity is evaluated (0.0 to 1.0) to dynamically adjust retrieval budgets and security filters.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-2">
              <div className="text-xs font-mono font-bold text-blue-600">02 / Hybrid Retrieval</div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Tri-Modal Memory</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                Fuses ChromaDB dense vector embeddings, BM25 keyword rankings, and Neo4j entity relationships via RRF.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-2">
              <div className="text-xs font-mono font-bold text-blue-600">03 / Grounding Critic</div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Atomic Fact Check</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                Every generated sentence is broken down into claims and verified against the context before release.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-2">
              <div className="text-xs font-mono font-bold text-blue-600">04 / Self-Heal Loop</div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Automated Retry</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                If claims fail verification, the Healer Agent automatically rewrites the query and re-retrieves.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════
         6. FEATURES / CAPABILITIES
         ════════════════════════════════════════════════════ */}
      <section id="features" className="scroll-mt-20 py-16 md:py-20 border-b border-slate-200/80 dark:border-slate-800/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="max-w-2xl mx-auto text-center mb-12">
            <span className="text-xs font-mono font-semibold text-blue-600 uppercase tracking-wider">
              Platform Features
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100 mt-1">
              Enterprise-Ready AI Infrastructure
            </h2>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-2">
              Engineered for data security, high-throughput streaming, and zero hallucinations.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 max-w-5xl mx-auto">
            <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-2">
              <div className="w-8 h-8 rounded-lg bg-blue-50 dark:bg-blue-950 text-blue-600 flex items-center justify-center">
                <Search size={16} />
              </div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Hybrid Search Fusion</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                Combines dense semantic vectors with BM25 sparse search and cross-encoder re-ranking for pinpoint precision.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-2">
              <div className="w-8 h-8 rounded-lg bg-emerald-50 dark:bg-emerald-950 text-emerald-600 flex items-center justify-center">
                <ShieldCheck size={16} />
              </div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Claim-Level Grounding</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                Deconstructs assistant outputs into individual factual claims, testing entailment against evidence.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-2">
              <div className="w-8 h-8 rounded-lg bg-amber-50 dark:bg-amber-950 text-amber-600 flex items-center justify-center">
                <RefreshCw size={16} />
              </div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Bounded Self-Correction</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                Autonomous heuristic retry loops that rewrite queries without entering infinite execution loops.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-2">
              <div className="w-8 h-8 rounded-lg bg-purple-50 dark:bg-purple-950 text-purple-600 flex items-center justify-center">
                <Workflow size={16} />
              </div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">LangGraph Orchestration</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                State machine routing across seven specialized agents with complete node-by-node inspectability.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-2">
              <div className="w-8 h-8 rounded-lg bg-cyan-50 dark:bg-cyan-950 text-cyan-600 flex items-center justify-center">
                <Sparkles size={16} />
              </div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Autonomous Scientist (AES)</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                Bayesian optimization that automatically tunes chunk sizes, top-k, and thresholds on a Pareto frontier.
              </p>
            </div>

            <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-2">
              <div className="w-8 h-8 rounded-lg bg-rose-50 dark:bg-rose-950 text-rose-600 flex items-center justify-center">
                <Lock size={16} />
              </div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Tenant Isolation &amp; RBAC</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                Cryptographically isolated data boundaries with RS256 JWT tokens and granular workspace roles.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════
         7. PIPELINE SECTION
         ════════════════════════════════════════════════════ */}
      <section id="pipeline" className="scroll-mt-20 py-16 md:py-20 border-b border-slate-200/80 dark:border-slate-800/80 bg-white/40 dark:bg-slate-900/40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="max-w-2xl mx-auto text-center mb-12">
            <span className="text-xs font-mono font-semibold text-blue-600 uppercase tracking-wider">
              Pipeline Architecture
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100 mt-1">
              Multi-Agent Graph Execution
            </h2>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-2">
              Inspect the exact sequential graph traversed during every single query.
            </p>
          </div>

          <div className="max-w-3xl mx-auto space-y-3">
            {[
              { num: "01", name: "Intake & Router", desc: "Enriches session context, sanitizes prompt injection attempts, and scores query complexity." },
              { num: "02", name: "Query Planner", desc: "Decomposes multi-intent queries and assigns adaptive retrieval budgets (k=3 to k=10)." },
              { num: "03", name: "Hybrid Retriever", desc: "Runs parallel dense vector search (ChromaDB) and BM25 sparse search with Reciprocal Rank Fusion." },
              { num: "04", name: "LLM Generator", desc: "Streams candidate answer synthesis anchored strictly to retrieved context chunks." },
              { num: "05", name: "Critic & Grader", desc: "Verifies atomic factual entailment against source documents (Threshold: 0.75)." },
              { num: "06", name: "Self-Healer Loop", desc: "When ungrounded claims appear, rewrites the query, retries retrieval, and regenerates." },
              { num: "07", name: "Verified Output", desc: "Emits final verified answer with source citations, latency metrics, and audit log trail." },
            ].map((st, i) => (
              <div
                key={i}
                className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs flex items-center gap-4"
              >
                <div className="w-8 h-8 rounded-lg bg-blue-50 dark:bg-blue-950/60 text-blue-600 font-mono font-bold text-xs flex items-center justify-center shrink-0">
                  {st.num}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-bold text-slate-900 dark:text-slate-100">
                    {st.name}
                  </div>
                  <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    {st.desc}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════
         8. METRICS / RELIABILITY
         ════════════════════════════════════════════════════ */}
      <section id="metrics" className="scroll-mt-20 py-16 md:py-20 border-b border-slate-200/80 dark:border-slate-800/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="max-w-2xl mx-auto text-center mb-12">
            <span className="text-xs font-mono font-semibold text-blue-600 uppercase tracking-wider">
              Operational Proof
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100 mt-1">
              Production Reliability Benchmarks
            </h2>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-2">
              Continuous validation against Golden Dataset evaluations and stress tests.
            </p>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 max-w-4xl mx-auto">
            <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-center shadow-xs">
              <div className="text-3xl font-extrabold text-slate-900 dark:text-slate-100 font-mono">
                98.4%
              </div>
              <div className="text-xs font-semibold text-slate-600 dark:text-slate-400 mt-1">
                Avg Grounding Score
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">RAGAS faithfulness verified</div>
            </div>

            <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-center shadow-xs">
              <div className="text-3xl font-extrabold text-blue-600 font-mono">
                &lt; 250ms
              </div>
              <div className="text-xs font-semibold text-slate-600 dark:text-slate-400 mt-1">
                P95 Retrieval Latency
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">Fast-Path cache optimization</div>
            </div>

            <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-center shadow-xs">
              <div className="text-3xl font-extrabold text-emerald-600 font-mono">
                99.1%
              </div>
              <div className="text-xs font-semibold text-slate-600 dark:text-slate-400 mt-1">
                Self-Healing Resolution
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">Automated query rewrites</div>
            </div>

            <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-center shadow-xs">
              <div className="text-3xl font-extrabold text-purple-600 font-mono">
                +14.8%
              </div>
              <div className="text-xs font-semibold text-slate-600 dark:text-slate-400 mt-1">
                Scientist Optimization
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">Bayesian Pareto frontier gain</div>
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════
         9. PRICING
         ════════════════════════════════════════════════════ */}
      <section id="pricing" className="scroll-mt-20 py-16 md:py-20 border-b border-slate-200/80 dark:border-slate-800/80 bg-white/40 dark:bg-slate-900/40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="max-w-2xl mx-auto text-center mb-12">
            <span className="text-xs font-mono font-semibold text-blue-600 uppercase tracking-wider">
              Transparent Pricing
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100 mt-1">
              Predictable Enterprise Plans
            </h2>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-2">
              Start free on developer tier or scale to enterprise clusters with dedicated compliance.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {/* Developer */}
            <div className="p-6 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col justify-between space-y-4">
              <div className="space-y-2">
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">Developer</h3>
                <p className="text-xs text-slate-500">For evaluation and small team knowledge bases.</p>
                <div className="pt-2">
                  <span className="text-3xl font-bold font-mono text-slate-900 dark:text-slate-100">$0</span>
                  <span className="text-xs text-slate-500 font-mono"> / month</span>
                </div>
              </div>
              <ul className="space-y-2 text-xs text-slate-600 dark:text-slate-400">
                <li className="flex items-center gap-2">
                  <CheckCircle size={13} className="text-emerald-500" />
                  <span>Up to 1,000 queries / mo</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle size={13} className="text-emerald-500" />
                  <span>Hybrid vector + BM25 search</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle size={13} className="text-emerald-500" />
                  <span>Critic grounding verification</span>
                </li>
              </ul>
              <Link
                href={signupDestination}
                className="w-full py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-800 dark:text-slate-200 font-semibold text-xs text-center transition-colors"
              >
                Get Started Free
              </Link>
            </div>

            {/* Production Team */}
            <div className="p-6 rounded-xl bg-white dark:bg-slate-900 border-2 border-blue-600 shadow-md relative flex flex-col justify-between space-y-4">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-2.5 py-0.5 rounded-full bg-blue-600 text-white font-mono text-[10px] font-semibold uppercase tracking-wider">
                Most Popular
              </div>
              <div className="space-y-2">
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">Production</h3>
                <p className="text-xs text-slate-500">For scaling applications requiring SLA guarantees.</p>
                <div className="pt-2">
                  <span className="text-3xl font-bold font-mono text-slate-900 dark:text-slate-100">$299</span>
                  <span className="text-xs text-slate-500 font-mono"> / month</span>
                </div>
              </div>
              <ul className="space-y-2 text-xs text-slate-600 dark:text-slate-400">
                <li className="flex items-center gap-2">
                  <CheckCircle size={13} className="text-blue-600" />
                  <span>50,000 queries / mo</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle size={13} className="text-blue-600" />
                  <span>Autonomous Experiment Scientist</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle size={13} className="text-blue-600" />
                  <span>Unlimited self-healing rewrites</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle size={13} className="text-blue-600" />
                  <span>99.9% uptime SLA</span>
                </li>
              </ul>
              <Link
                href={signupDestination}
                className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs text-center transition-colors shadow-xs"
              >
                Deploy Production
              </Link>
            </div>

            {/* Enterprise */}
            <div className="p-6 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col justify-between space-y-4">
              <div className="space-y-2">
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">Enterprise</h3>
                <p className="text-xs text-slate-500">Dedicated VPC, private clusters, and custom SLAs.</p>
                <div className="pt-2">
                  <span className="text-3xl font-bold font-mono text-slate-900 dark:text-slate-100">Custom</span>
                </div>
              </div>
              <ul className="space-y-2 text-xs text-slate-600 dark:text-slate-400">
                <li className="flex items-center gap-2">
                  <CheckCircle size={13} className="text-emerald-500" />
                  <span>Unlimited query volume</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle size={13} className="text-emerald-500" />
                  <span>Dedicated VPC / on-prem deployment</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle size={13} className="text-emerald-500" />
                  <span>SOC-2 &amp; HIPAA BAA signing</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle size={13} className="text-emerald-500" />
                  <span>24/7 dedicated engineering support</span>
                </li>
              </ul>
              <a
                href="mailto:enterprise@nexuscore.ai"
                className="w-full py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-800 dark:text-slate-200 font-semibold text-xs text-center transition-colors"
              >
                Contact Enterprise Sales
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════
         10. FINAL CALL TO ACTION
         ════════════════════════════════════════════════════ */}
      <section className="py-16 md:py-20 text-center">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 space-y-5">
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
            Ready to deploy self-healing knowledge intelligence?
          </h2>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 max-w-xl mx-auto leading-relaxed">
            Eliminate hallucinations. Empower your teams and systems with verifiable, grounded answers.
          </p>
          <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href={signupDestination}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs sm:text-sm shadow-sm transition-all"
            >
              <span>Get Started Free</span>
              <ArrowRight size={14} />
            </Link>
            <Link
              href="/docs"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-800 font-semibold text-xs sm:text-sm transition-colors"
            >
              <BookOpen size={13} />
              <span>Read Documentation</span>
            </Link>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════
         11. FOOTER
         ════════════════════════════════════════════════════ */}
      <footer className="border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-8 text-xs">
            <div className="col-span-2 md:col-span-1 space-y-3">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center text-white">
                  <Brain size={14} />
                </div>
                <span className="font-bold text-sm text-slate-900 dark:text-slate-100">
                  Nexus Core
                </span>
              </div>
              <p className="text-slate-500 leading-relaxed">
                Self-healing multi-agent RAG platform with Autonomous Experiment Scientist optimization.
              </p>
            </div>

            <div>
              <h4 className="font-bold text-slate-900 dark:text-slate-100 mb-2 uppercase tracking-wider text-[11px]">
                Product
              </h4>
              <ul className="space-y-1.5 text-slate-600 dark:text-slate-400">
                <li><a href="#features" className="hover:text-blue-600 transition-colors">Features</a></li>
                <li><a href="#pipeline" className="hover:text-blue-600 transition-colors">AI Pipeline</a></li>
                <li><a href="#pricing" className="hover:text-blue-600 transition-colors">Pricing</a></li>
                <li><Link href="/docs" className="hover:text-blue-600 transition-colors">Documentation</Link></li>
              </ul>
            </div>

            <div>
              <h4 className="font-bold text-slate-900 dark:text-slate-100 mb-2 uppercase tracking-wider text-[11px]">
                Workspaces
              </h4>
              <ul className="space-y-1.5 text-slate-600 dark:text-slate-400">
                <li><Link href="/app/dashboard" className="hover:text-blue-600 transition-colors">Dashboard</Link></li>
                <li><Link href="/app/query" className="hover:text-blue-600 transition-colors">Live Query</Link></li>
                <li><Link href="/app/pipeline" className="hover:text-blue-600 transition-colors">Pipeline Graph</Link></li>
                <li><Link href="/app/documents" className="hover:text-blue-600 transition-colors">Documents</Link></li>
              </ul>
            </div>

            <div>
              <h4 className="font-bold text-slate-900 dark:text-slate-100 mb-2 uppercase tracking-wider text-[11px]">
                Security
              </h4>
              <ul className="space-y-1.5 text-slate-600 dark:text-slate-400">
                <li><span className="text-slate-500">Tenant Isolation</span></li>
                <li><span className="text-slate-500">RS256 JWT Signing</span></li>
                <li><span className="text-slate-500">SOC-2 Type II Certified</span></li>
                <li><span className="text-slate-500">Audit Trail Logs</span></li>
              </ul>
            </div>
          </div>

          <div className="pt-6 border-t border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-400">
            <p>&copy; {new Date().getFullYear()} Nexus Core | Self-Healing RAG. All rights reserved.</p>
            <div className="flex items-center gap-4">
              <a href="#how-it-works" className="hover:text-slate-600 dark:hover:text-slate-300">Architecture</a>
              <Link href="/docs" className="hover:text-slate-600 dark:hover:text-slate-300">API Reference</Link>
              <Link href={appDestination} className="hover:text-blue-600 font-medium">Console Login</Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}