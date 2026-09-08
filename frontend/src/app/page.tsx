"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import ThemeToggle from "@/components/ThemeToggle";
import {
  ArrowRight,
  Brain,
  Globe,
  Shield,
  Zap,
  Layers,
  CheckCircle,
  Cpu,
  BarChart3,
  GitBranch,
  Search,
  BookOpen,
  Star,
  Users,
  MessageSquare,
  Database,
  Sparkles,
  ChevronDown,
  Menu,
  X,
  Quote,
  Building2,
  Lock,
  Cloud,
  Code2,
  ExternalLink,
  Mail,
  ChevronRight,
  Play,
  Pause,
  RefreshCw,
  FileText,
  Network,
  Hexagon,
  Activity,
  TrendingUp,
  PieChart,
  Clock,
  Timer,
  Award,
  Rocket,
  Lightbulb,
  Target,
  Eye,
  Workflow,
  ArrowDown,
} from "lucide-react";

/* ─── Animated Counter ───────────────────────────────── */
function AnimatedCounter({ end, suffix = "", duration = 2000 }: { end: number; suffix?: string; duration?: number }) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const counted = useRef(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !counted.current) {
          counted.current = true;
          const startTime = Date.now();
          const tick = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            setCount(Math.floor(eased * end));
            if (progress < 1) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
        }
      },
      { threshold: 0.3 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [end, duration]);

  return <span ref={ref}>{count}{suffix}</span>;
}

/* ─── Typewriter Effect ──────────────────────────────── */
function TypewriterText({ words }: { words: string[] }) {
  const [wordIndex, setWordIndex] = useState(0);
  const [charIndex, setCharIndex] = useState(0);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const currentWord = words[wordIndex];
    let timeout: NodeJS.Timeout;

    if (!isDeleting && charIndex < currentWord.length) {
      timeout = setTimeout(() => setCharIndex((c) => c + 1), 80);
    } else if (!isDeleting && charIndex === currentWord.length) {
      timeout = setTimeout(() => setIsDeleting(true), 1500);
    } else if (isDeleting && charIndex > 0) {
      timeout = setTimeout(() => setCharIndex((c) => c - 1), 40);
    } else if (isDeleting && charIndex === 0) {
      setIsDeleting(false);
      setWordIndex((i) => (i + 1) % words.length);
    }

    return () => clearTimeout(timeout);
  }, [charIndex, isDeleting, wordIndex, words]);

  return (
    <span className="text-gradient inline-block min-w-[20px]">
      {words[wordIndex].slice(0, charIndex)}
      <span className="animate-pulse" style={{ color: "#6366f1" }}>|</span>
    </span>
  );
}

/* ─── Particles Background ───────────────────────────── */
function ParticlesBg() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let frame = 0;
    const PARTICLE_COUNT = 50;
    const CONNECT_DIST = 100;
    const CONNECT_DIST_SQ = CONNECT_DIST * CONNECT_DIST;
    const particles: { x: number; y: number; vx: number; vy: number; size: number; alpha: number }[] = [];

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        size: Math.random() * 1.5 + 0.5,
        alpha: Math.random() * 0.3 + 0.1,
      });
    }

    const draw = () => {
      frame++;
      // Skip every other frame → ~30fps to reduce CPU
      if (frame % 2 === 0) { animId = requestAnimationFrame(draw); return; }

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      for (let i = 0; i < PARTICLE_COUNT; i++) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(var(--particle-color, 165, 180, 252), ${p.alpha})`;
        ctx.fill();

        for (let j = i + 1; j < PARTICLE_COUNT; j++) {
          const dx = p.x - particles[j].x;
          const dy = p.y - particles[j].y;
          // Use squared distance — avoids expensive Math.sqrt
          const distSq = dx * dx + dy * dy;
          if (distSq < CONNECT_DIST_SQ) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(var(--particle-link, 99, 102, 241), ${0.04 * (1 - distSq / CONNECT_DIST_SQ)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }

      animId = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={canvasRef} className="fixed inset-0 pointer-events-none z-0" />;
}

/* ─── Floating Gradient Orbs ─────────────────────────── */
function FloatingOrbs() {
  return (
    <>
      <div className="hero-orb-1" />
      <div className="hero-orb-2" />
      <div
        className="absolute top-1/3 left-1/4 w-[500px] h-[500px] rounded-full pointer-events-none"
        style={{
          background: "radial-gradient(circle, rgba(168,85,247,0.08) 0%, transparent 70%)",
          filter: "blur(100px)",
          animation: "orbMove 20s ease-in-out infinite",
        }}
      />
      <div
        className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] rounded-full pointer-events-none"
        style={{
          background: "radial-gradient(circle, rgba(6,182,212,0.06) 0%, transparent 70%)",
          filter: "blur(100px)",
          animation: "orbMove 18s ease-in-out infinite reverse",
        }}
      />
    </>
  );
}

/* ─── Navbar ─────────────────────────────────────────── */
function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled ? "bg-white/80 backdrop-blur-md shadow-xs" : "bg-transparent"
      }`}
      style={{ borderBottom: scrolled ? "1px solid var(--border-default)" : "1px solid transparent" }}
    >
      <div className="section-container flex items-center justify-between h-16">
        <a href="/" className="flex items-center gap-2.5 group">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-300 group-hover:shadow-lg group-hover:scale-105"
            style={{ background: "linear-gradient(135deg, #2563eb, #4f46e5)" }}
          >
            <Brain size={16} className="text-white" />
          </div>
          <span className="text-sm font-semibold tracking-tight" style={{ color: "var(--text-primary)" }}>
            Nexus Core
          </span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded"
            style={{ background: "var(--bg-hover)", color: "var(--text-muted)", border: "1px solid var(--border-default)" }}>
            v2.4 Production
          </span>
        </a>

        {/* Desktop Links */}
        <div className="hidden md:flex items-center gap-1">
          <a href="#features" className="btn btn-ghost text-xs">Features</a>
          <a href="#how-it-works" className="btn btn-ghost text-xs">How It Works</a>
          <a href="#pipeline" className="btn btn-ghost text-xs">Pipeline</a>
          <a href="#stats" className="btn btn-ghost text-xs">Metrics</a>
          <a href="#pricing" className="btn btn-ghost text-xs">Pricing</a>
          <a href="/docs" className="btn btn-ghost text-xs">Docs</a>
          <a href="/dashboard" className="btn btn-primary text-xs ml-2">
            Launch App <ArrowRight size={12} />
          </a>
          <ThemeToggle />
        </div>

        <div className="flex items-center gap-2 md:hidden">
          <ThemeToggle />
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="flex items-center justify-center w-9 h-9 rounded-lg transition-all hover:bg-white/5"
            style={{ color: "var(--text-secondary)" }}
            aria-label="Toggle menu"
          >
          {mobileOpen ? <X size={16} /> : <Menu size={16} />}
        </button>
      </div>

      </div>

      {mobileOpen && (
        <div className="md:hidden glass-strong p-4" style={{ borderTop: "1px solid var(--border-default)" }}>
          <div className="flex flex-col gap-2">
            <a href="#features" onClick={() => setMobileOpen(false)} className="btn btn-ghost justify-start text-xs">Features</a>
            <a href="#how-it-works" onClick={() => setMobileOpen(false)} className="btn btn-ghost justify-start text-xs">How It Works</a>
            <a href="#pipeline" onClick={() => setMobileOpen(false)} className="btn btn-ghost justify-start text-xs">Pipeline</a>
            <a href="#stats" onClick={() => setMobileOpen(false)} className="btn btn-ghost justify-start text-xs">Metrics</a>
            <a href="#pricing" onClick={() => setMobileOpen(false)} className="btn btn-ghost justify-start text-xs">Pricing</a>
            <a href="/docs" onClick={() => setMobileOpen(false)} className="btn btn-ghost justify-start text-xs">Docs</a>
            <a href="/dashboard" onClick={() => setMobileOpen(false)} className="btn btn-primary justify-center text-xs mt-2">
              Launch App <ArrowRight size={12} />
            </a>
          </div>
        </div>
      )}
    </nav>
  );
}

/* ─── Feature Card ───────────────────────────────────── */
function FeatureCard({ icon, title, desc, gradient, delay = 0 }: { icon: React.ReactNode; title: string; desc: string; gradient: string; delay?: number }) {
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setIsVisible(true); observer.disconnect(); } },
      { threshold: 0.1 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className="bento-card group p-6 sm:p-7"
      style={{
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? "translateY(0)" : "translateY(20px)",
        transition: `all 0.6s ease ${delay}s`,
      }}
    >
      <div
        className="w-10 h-10 rounded-xl flex items-center justify-center mb-4 transition-all duration-300 group-hover:scale-110 group-hover:shadow-lg"
        style={{ background: gradient, boxShadow: "0 4px 12px rgba(0,0,0,0.3)" }}
      >
        {icon}
      </div>
      <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--text-primary)" }}>{title}</h3>
      <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>{desc}</p>
    </div>
  );
}

/* ─── Pipeline Step ──────────────────────────────────── */
function PipelineStep({ num, label, desc, color, delay = 0 }: { num: number; label: string; desc: string; color: string; delay?: number }) {
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setIsVisible(true); observer.disconnect(); } },
      { threshold: 0.2 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className="flex items-start gap-5 group"
      style={{
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? "translateX(0)" : "translateX(-20px)",
        transition: `all 0.5s ease ${delay}s`,
      }}
    >
      <div
        className="w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold shrink-0 transition-all duration-300 group-hover:scale-110 group-hover:shadow-lg"
        style={{ background: color, boxShadow: `0 0 20px ${color}40` }}
      >
        {num}
      </div>
      <div className="pt-1.5">
        <h4 className="text-sm font-semibold mb-1" style={{ color: "var(--text-primary)" }}>{label}</h4>
        <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>{desc}</p>
      </div>
    </div>
  );
}

/* ─── Stats Card ─────────────────────────────────────── */
function StatsCard({ icon, label, end, suffix = "" }: { icon: React.ReactNode; label: string; end: number; suffix?: string }) {
  return (
    <div className="text-center p-6">
      <div className="flex justify-center mb-3" style={{ color: "var(--text-accent)" }}>
        {icon}
      </div>
      <div className="text-3xl sm:text-4xl font-bold font-mono mb-1 text-gradient" style={{ lineHeight: 1.1 }}>
        <AnimatedCounter end={end} suffix={suffix} />
      </div>
      <div className="text-xs" style={{ color: "var(--text-secondary)" }}>{label}</div>
    </div>
  );
}

/* ─── Testimonial Card ───────────────────────────────── */
function TestimonialCard({ quote, author, role, avatar, rating }: { quote: string; author: string; role: string; avatar: string; rating: number }) {
  return (
    <div
      className="rounded-xl p-6 transition-all duration-300 hover:shadow-md bg-white border border-slate-200/80"
    >
      <div className="flex gap-1 mb-4">
        {Array.from({ length: rating }).map((_, i) => (
          <Star key={i} size={12} style={{ color: "#f59e0b", fill: "#f59e0b" }} />
        ))}
      </div>
      <Quote size={16} className="mb-2 text-slate-400" />
      <p className="text-xs leading-relaxed mb-4 text-slate-600">
        &ldquo;{quote}&rdquo;
      </p>
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white bg-gradient-to-br from-blue-600 to-indigo-600">
          {avatar}
        </div>
        <div>
          <div className="text-xs font-semibold text-slate-900">{author}</div>
          <div className="text-[10px] text-slate-500">{role}</div>
        </div>
      </div>
    </div>
  );
}

/* ─── Pricing Card ───────────────────────────────────── */
function PricingCard({ name, desc, price, features, cta, popular = false }: { name: string; desc: string; price: string; features: string[]; cta: string; popular?: boolean }) {
  return (
    <div
      className={`rounded-xl p-6 transition-all duration-300 relative bg-white ${
        popular
          ? "border-2 border-blue-600 shadow-md ring-1 ring-blue-500/20"
          : "border border-slate-200/80 shadow-xs"
      }`}
    >
      {popular && (
        <div
          className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-[10px] font-semibold text-white bg-gradient-to-r from-blue-600 to-indigo-600 shadow-xs"
        >
          Most Popular
        </div>
      )}
      <h3 className="text-sm font-bold mb-1 text-slate-900">{name}</h3>
      <p className="text-xs mb-4 text-slate-500">{desc}</p>
      <div className="mb-4">
        <span className="text-3xl font-bold font-mono text-slate-900">{price}</span>
        {price !== "Custom" && <span className="text-xs ml-1 text-slate-500">/month</span>}
      </div>
      <ul className="space-y-2 mb-6">
        {features.map((f, i) => (
          <li key={i} className="flex items-center gap-2 text-xs text-slate-600">
            <CheckCircle size={12} className="text-emerald-600 shrink-0" />
            {f}
          </li>
        ))}
      </ul>
      <a
        href="/dashboard"
        className={`block text-center py-2.5 rounded-lg text-xs font-semibold transition-all ${
          popular
            ? "bg-blue-600 hover:bg-blue-700 text-white shadow-xs"
            : "bg-slate-50 hover:bg-slate-100 text-slate-800 border border-slate-200"
        }`}
      >
        {cta}
      </a>
    </div>
  );
}

/* ─── FAQ Accordion ──────────────────────────────────── */
function FAQItem({ question, answer }: { question: string; answer: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      className="rounded-xl overflow-hidden transition-all duration-200"
      style={{ border: "1px solid rgba(255,255,255,0.05)" }}
    >
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 text-left text-xs font-medium transition-colors hover:bg-white/[0.02]"
        style={{ color: "var(--text-primary)" }}
      >
        {question}
        <ChevronDown
          size={12}
          className="transition-transform duration-200"
          style={{
            transform: open ? "rotate(180deg)" : "rotate(0deg)",
            color: "var(--text-muted)",
          }}
        />
      </button>
      <div
        className="overflow-hidden transition-all duration-200"
        style={{
          maxHeight: open ? "200px" : "0px",
          opacity: open ? 1 : 0,
        }}
      >
        <p className="px-4 pb-4 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
          {answer}
        </p>
      </div>
    </div>
  );
}

/* ─── Logo Marquee ───────────────────────────────────── */
function LogoMarquee() {
  const logos = [
    "OpenAI", "LangChain", "Neo4j", "ChromaDB", "Python", "TypeScript",
    "Docker", "Kubernetes", "PostgreSQL", "Redis", "Next.js", "React",
  ];
  return (
    <div className="relative overflow-hidden py-8">
      <div
        className="absolute inset-y-0 left-0 w-20 z-10"
        style={{ background: "linear-gradient(90deg, #0a0a0f, transparent)" }}
      />
      <div
        className="absolute inset-y-0 right-0 w-20 z-10"
        style={{ background: "linear-gradient(270deg, #0a0a0f, transparent)" }}
      />
      <div className="flex gap-8 animate-marquee whitespace-nowrap">
        {[...logos, ...logos].map((name, i) => (
          <span
            key={i}
            className="text-sm font-semibold tracking-wide"
            style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}
          >
            {name}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ─── Footer ─────────────────────────────────────────── */
function Footer() {
  return (
    <footer className="border-t border-slate-200/90 bg-white">
      <div className="section-container py-16">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-12">
          <div className="col-span-2 md:col-span-1">
            <div className="flex items-center gap-2.5 mb-3">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-gradient-to-br from-blue-600 to-indigo-600 shadow-2xs">
                <Brain size={14} className="text-white" />
              </div>
              <span className="text-sm font-bold text-slate-900">Nexus Core</span>
            </div>
            <p className="text-xs leading-relaxed text-slate-500">
              Self-healing multi-agent RAG platform with Autonomous Experiment Scientist (AES) for automated, production-grade optimization.
            </p>
          </div>
          <div>
            <h4 className="text-[11px] font-bold uppercase tracking-wider mb-3 text-slate-900">Product</h4>
            <div className="space-y-2 text-xs">
              <a href="#features" className="block text-slate-600 hover:text-blue-600 transition-colors">Features</a>
              <a href="#pricing" className="block text-slate-600 hover:text-blue-600 transition-colors">Pricing</a>
              <a href="/docs" className="block text-slate-600 hover:text-blue-600 transition-colors">Documentation</a>
              <a href="/dashboard" className="block text-slate-600 hover:text-blue-600 transition-colors">Dashboard</a>
            </div>
          </div>
          <div>
            <h4 className="text-[11px] font-bold uppercase tracking-wider mb-3 text-slate-900">Company</h4>
            <div className="space-y-2 text-xs">
              <a href="#" className="block text-slate-600 hover:text-blue-600 transition-colors">About</a>
              <a href="#" className="block text-slate-600 hover:text-blue-600 transition-colors">Blog</a>
              <a href="#" className="block text-slate-600 hover:text-blue-600 transition-colors">Careers</a>
              <a href="#" className="block text-slate-600 hover:text-blue-600 transition-colors">Contact</a>
            </div>
          </div>
          <div>
            <h4 className="text-[11px] font-bold uppercase tracking-wider mb-3 text-slate-900">Legal</h4>
            <div className="space-y-2 text-xs">
              <a href="#" className="block text-slate-600 hover:text-blue-600 transition-colors">Privacy</a>
              <a href="#" className="block text-slate-600 hover:text-blue-600 transition-colors">Terms</a>
              <a href="#" className="block text-slate-600 hover:text-blue-600 transition-colors">Security</a>
              <a href="#" className="block text-slate-600 hover:text-blue-600 transition-colors">SOC 2</a>
            </div>
          </div>
        </div>
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 pt-8 border-t border-slate-100">
          <p className="text-xs text-slate-500">
            &copy; {new Date().getFullYear()} Nexus Core | Self-Healing RAG. All rights reserved.
          </p>
          <div className="flex items-center gap-3 text-slate-400">
            <a href="#" className="p-1.5 rounded-lg hover:text-slate-700 hover:bg-slate-100 transition-colors">
              <GitBranch size={14} />
            </a>
            <a href="#" className="p-1.5 rounded-lg hover:text-slate-700 hover:bg-slate-100 transition-colors">
              <MessageSquare size={14} />
            </a>
            <a href="#" className="p-1.5 rounded-lg hover:text-slate-700 hover:bg-slate-100 transition-colors">
              <Globe size={14} />
            </a>
            <a href="#" className="p-1.5 rounded-lg hover:text-slate-700 hover:bg-slate-100 transition-colors">
              <Mail size={14} />
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}

/* ─── MAIN LANDING PAGE ──────────────────────────────── */
export default function LandingPage() {
  return (
    <>
      <ParticlesBg />
      <FloatingOrbs />
      <Navbar />

      <main className="relative z-10">
        {/* ════════════════════════════════════════════════
           HERO
           ════════════════════════════════════════════════ */}
        <section className="relative min-h-screen flex items-center justify-center overflow-hidden pt-16">
          <div
            className="absolute inset-0"
            style={{
              background: "radial-gradient(ellipse 60% 40% at 50% 0%, rgba(99,102,241,0.08) 0%, transparent 70%)",
            }}
          />

          <div className="section-container w-full pb-12">
            <div className="max-w-3xl mx-auto text-center">
              {/* Badge */}
              <div
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium mb-6"
                style={{
                  background: "rgba(99,102,241,0.08)",
                  border: "1px solid rgba(99,102,241,0.2)",
                  color: "var(--text-accent)",
                }}
              >
                <Sparkles size={12} />
                <span className="animate-shimmer" style={{ backgroundSize: "200% auto" }}>Self-Healing RAG — Now Available</span>
              </div>

              {/* Heading */}
              <h1
                className="text-4xl sm:text-5xl md:text-6xl font-bold tracking-tight leading-[1.08] mb-4"
              >
                Knowledge That{" "}
                <span className="text-gradient">Heals Itself</span>
                <br />
                <TypewriterText words={["Answers You Can Trust.", "Zero Hallucinations.", "Enterprise-Grade AI."]} />
              </h1>

              {/* Subtitle */}
              <p
                className="text-base sm:text-lg max-w-xl mx-auto mb-8 leading-relaxed"
                style={{ color: "var(--text-secondary)" }}
              >
                Nexus Core is an enterprise-grade multi-agent RAG platform that
                detects hallucinations, self-corrects in real-time, and delivers
                <span style={{ color: "var(--text-primary)" }}> verified, factual answers</span> from your knowledge base.
              </p>

              {/* CTA Buttons */}
              <div
                className="flex flex-col sm:flex-row items-center justify-center gap-3"
              >
                <a
                  href="/dashboard"
                  className="btn-primary px-6 py-3 text-sm inline-flex items-center gap-2"
                  style={{ borderRadius: "12px", fontSize: "14px" }}
                >
                  Get Started <ArrowRight size={14} />
                </a>
                <a
                  href="#how-it-works"
                  className="btn-outline px-6 py-3 text-sm inline-flex items-center gap-2"
                  style={{ borderRadius: "12px", fontSize: "14px" }}
                >
                  <Play size={12} /> See How It Works
                </a>
              </div>

              {/* Scroll indicator */}
              <div className="mt-10 animate-float">
                <ChevronDown size={20} style={{ color: "var(--text-muted)" }} />
              </div>
            </div>
          </div>
        </section>

        {/* ════════════════════════════════════════════════
           LOGO MARQUEE
           ════════════════════════════════════════════════ */}
        <section className="py-8">
          <div className="section-container">
            <p className="text-[9px] text-center uppercase tracking-widest mb-4" style={{ color: "var(--text-muted)" }}>
              Built with industry-leading technology
            </p>
            <LogoMarquee />
          </div>
        </section>

        {/* ════════════════════════════════════════════════
           FEATURES
           ════════════════════════════════════════════════ */}
        <section id="features" className="py-24 md:py-32">
          <div className="section-container">
            <div className="max-w-2xl mx-auto text-center mb-16">
              <div className="label mb-4" style={{ color: "var(--text-accent)" }}>Platform Capabilities</div>
              <h2 className="text-2xl sm:text-3xl font-bold mb-4">
                Enterprise-grade{" "}
                <span className="text-gradient">intelligence</span>
              </h2>
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                Seven specialized agents work in concert to retrieve, generate, verify, 
                and heal knowledge in real-time.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <FeatureCard
                icon={<Search size={18} className="text-white" />}
                gradient="linear-gradient(135deg, #6366f1, #4f46e5)"
                title="Hybrid Retrieval"
                desc="BM25 + dense vector search with cross-encoder re-ranking via ChromaDB, RRF fusion, and Neo4j graph traversal for maximum precision."
                delay={0}
              />
              <FeatureCard
                icon={<Shield size={18} className="text-white" />}
                gradient="linear-gradient(135deg, #10b981, #059669)"
                title="Hallucination Detection"
                desc="Critic Agent decomposes every claim and verifies against retrieved context using groundedness scoring &mdash; no more AI fabrications."
                delay={0.1}
              />
              <FeatureCard
                icon={<Cpu size={18} className="text-white" />}
                gradient="linear-gradient(135deg, #f59e0b, #ef4444)"
                title="Self-Healing Pipeline"
                desc="When hallucination is detected, the Healer Agent rewrites the query and re-retrieves automatically &mdash; zero manual intervention."
                delay={0.2}
              />
              <FeatureCard
                icon={<GitBranch size={18} className="text-white" />}
                gradient="linear-gradient(135deg, #06b6d4, #3b82f6)"
                title="Multi-Agent Graph"
                desc="LangGraph orchestration routes queries through Intake, Planner, Retriever, Generator, Critic, and Output with branching recovery paths."
                delay={0.3}
              />
              <FeatureCard
                icon={<Database size={18} className="text-white" />}
                gradient="linear-gradient(135deg, #a855f7, #d946ef)"
                title="Graph-Augmented RAG"
                desc="Neo4j knowledge graph enriches retrieval with entity relationships, enabling contextual answers beyond flat vector search."
                delay={0.4}
              />
              <FeatureCard
                icon={<BarChart3 size={18} className="text-white" />}
                gradient="linear-gradient(135deg, #14b8a6, #0d9488)"
                title="Enterprise Observability"
                desc="Full telemetry, audit logging, RBAC, rate limiting, and concurrency management. Built for production from day one."
                delay={0.5}
              />
            </div>
          </div>
        </section>

        {/* ════════════════════════════════════════════════
           HOW IT WORKS (Interactive Demo)
           ════════════════════════════════════════════════ */}
        <section id="how-it-works" className="py-24 md:py-32 relative">
          <div className="absolute inset-0" style={{
            background: "radial-gradient(ellipse 50% 50% at 50% 50%, rgba(99,102,241,0.03) 0%, transparent 70%)",
          }} />

          <div className="section-container">
            <div className="max-w-2xl mx-auto text-center mb-16">
              <div className="label mb-4" style={{ color: "var(--text-accent)" }}>How It Works</div>
              <h2 className="text-2xl sm:text-3xl font-bold mb-4">
                From question to{" "}
                <span className="text-gradient-accent">verified answer</span>
              </h2>
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                Every query flows through a rigorous verification loop. If a hallucination is detected, the system heals itself automatically.
              </p>
            </div>

            {/* Flow Diagram */}
            <div className="max-w-4xl mx-auto">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
                {[
                  { step: "01", label: "Query Intake", color: "#6366f1", desc: "Parse & validate" },
                  { step: "02", label: "Plan & Retrieve", color: "#06b6d4", desc: "Hybrid search + graph" },
                  { step: "03", label: "Generate & Verify", color: "#f59e0b", desc: "LLM + Critic agent" },
                  { step: "04", label: "Output", color: "#10b981", desc: "Verified answer" },
                ].map((item, i) => (
                  <div key={i} className="text-center p-4 rounded-xl transition-all hover:bg-white/[0.02] group">
                    <div
                      className="w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-3 text-sm font-bold transition-all group-hover:scale-110 group-hover:shadow-lg"
                      style={{ background: `${item.color}20`, color: item.color, border: `1px solid ${item.color}30` }}
                    >
                      {item.step}
                    </div>
                    <h4 className="text-xs font-semibold mb-1" style={{ color: "var(--text-primary)" }}>{item.label}</h4>
                    <p className="text-[10px]" style={{ color: "var(--text-muted)" }}>{item.desc}</p>
                  </div>
                ))}
              </div>

              {/* Healing Loop Highlight */}
              <div
                className="rounded-xl p-6 text-center relative overflow-hidden"
                style={{
                  background: "linear-gradient(135deg, rgba(239,68,68,0.04), rgba(245,158,11,0.04))",
                  border: "1px solid rgba(239,68,68,0.12)",
                }}
              >
                <div className="relative z-10">
                  <RefreshCw size={20} className="mx-auto mb-2" style={{ color: "#f59e0b" }} />
                  <h4 className="text-sm font-semibold mb-1" style={{ color: "var(--text-primary)" }}>
                    Self-Healing Loop
                  </h4>
                  <p className="text-[11px]" style={{ color: "var(--text-secondary)" }}>
                    If the Critic Agent detects an unverifiable claim, the <strong style={{ color: "#f59e0b" }}>Healer Agent</strong> automatically rewrites the query, re-retrieves from the knowledge base, and regenerates the answer &mdash; all in milliseconds, with zero human intervention.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ════════════════════════════════════════════════
           PIPELINE
           ════════════════════════════════════════════════ */}
        <section id="pipeline" className="py-24 md:py-32">
          <div className="section-container">
            <div className="max-w-2xl mx-auto text-center mb-16">
              <div className="label mb-4" style={{ color: "var(--text-accent)" }}>Architecture</div>
              <h2 className="text-2xl sm:text-3xl font-bold mb-4">
                Deep dive into the{" "}
                <span className="text-gradient-accent">pipeline</span>
              </h2>
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                Every query passes through a rigorous multi-agent verification loop. 
                If a hallucination is detected, the system heals itself automatically.
              </p>
            </div>

            <div className="max-w-2xl mx-auto space-y-8">
              <PipelineStep num={1} color="linear-gradient(135deg, #6366f1, #4f46e5)" label="Intake & Planner" desc="Query is received, analyzed for intent, and decomposed into a retrieval plan." delay={0} />
              <div className="h-6 w-px mx-auto" style={{ background: "linear-gradient(180deg, rgba(255,255,255,0.06), transparent)" }} />
              <PipelineStep num={2} color="linear-gradient(135deg, #06b6d4, #3b82f6)" label="Hybrid Retrieval" desc="Searches vector store (ChromaDB), knowledge graph (Neo4j), and BM25 index. Results fused via RRF and re-ranked." delay={0.1} />
              <div className="h-6 w-px mx-auto" style={{ background: "linear-gradient(180deg, rgba(255,255,255,0.06), transparent)" }} />
              <PipelineStep num={3} color="linear-gradient(135deg, #f59e0b, #d97706)" label="Generation" desc="LLM generates a contextual answer using the retrieved chunks and query plan." delay={0.2} />
              <div className="h-6 w-px mx-auto" style={{ background: "linear-gradient(180deg, rgba(255,255,255,0.06), transparent)" }} />
              <PipelineStep num={4} color="linear-gradient(135deg, #10b981, #059669)" label="Critic & Verification" desc="Every factual claim is extracted, grounded against retrieved context, and scored. Verified answers proceed to output." delay={0.3} />
              <div className="h-6 w-px mx-auto" style={{ background: "linear-gradient(180deg, rgba(255,255,255,0.06), transparent)" }} />
              <PipelineStep num={5} color="linear-gradient(135deg, #ef4444, #dc2626)" label="Self-Heal (if needed)" desc="Unverified claims trigger the Healer Agent: query is rewritten, retrieval retried, and the answer regenerated." delay={0.4} />
              <div className="h-6 w-px mx-auto" style={{ background: "linear-gradient(180deg, rgba(255,255,255,0.06), transparent)" }} />
              <PipelineStep num={6} color="linear-gradient(135deg, #a855f7, #d946ef)" label="Verified Output" desc="The final answer is delivered along with confidence scores, source citations, and audit trail." delay={0.5} />
            </div>
          </div>
        </section>

        {/* ════════════════════════════════════════════════
           STATS
           ════════════════════════════════════════════════ */}
        <section id="stats" className="py-24 md:py-32">
          <div className="section-container">
            <div
              className="rounded-2xl overflow-hidden relative"
              style={{
                background: "linear-gradient(135deg, rgba(99,102,241,0.04), rgba(139,92,246,0.04))",
                border: "1px solid rgba(99,102,241,0.1)",
              }}
            >
              <div className="absolute inset-0" style={{
                background: "radial-gradient(ellipse 60% 60% at 50% 50%, rgba(99,102,241,0.04) 0%, transparent 70%)",
              }} />
              
              <div className="relative z-10 px-8 py-12 md:py-16">
                <div className="text-center mb-10">
                  <div className="label mb-3" style={{ color: "var(--text-accent)" }}>Key Metrics</div>
                  <h2 className="text-2xl sm:text-3xl font-bold">
                    Trusted by <span className="text-gradient">intelligent</span> systems
                  </h2>
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <StatsCard icon={<MessageSquare size={20} />} label="Queries Processed" end={12847} suffix="+" />
                  <StatsCard icon={<Brain size={20} />} label="Avg. Confidence" end={97} suffix="%" />
                  <StatsCard icon={<Zap size={20} />} label="Avg. Response Time" end={240} suffix="ms" />
                  <StatsCard icon={<CheckCircle size={20} />} label="Self-Heals Triggered" end={342} suffix="" />
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ════════════════════════════════════════════════
           TESTIMONIALS
           ════════════════════════════════════════════════ */}
        <section id="testimonials" className="py-24 md:py-32">
          <div className="section-container">
            <div className="max-w-2xl mx-auto text-center mb-16">
              <div className="label mb-4" style={{ color: "var(--text-accent)" }}>Testimonials</div>
              <h2 className="text-2xl sm:text-3xl font-bold mb-4">
                Loved by{" "}
                <span className="text-gradient">engineering teams</span>
              </h2>
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                See what teams are saying about Nexus Core.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <TestimonialCard
                quote="Nexus Core eliminated hallucinations in our RAG pipeline. The self-healing mechanism saved us countless hours of manual verification."
                author="Alex Chen"
                role="CTO, DataForge AI"
                avatar="AC"
                rating={5}
              />
              <TestimonialCard
                quote="The multi-agent architecture is brilliant. We saw a 40% improvement in answer accuracy within the first week of deployment."
                author="Sarah Mitchell"
                role="VP Engineering, CogniLab"
                avatar="SM"
                rating={5}
              />
              <TestimonialCard
                quote="Enterprise-grade observability and security out of the box. It integrated seamlessly with our existing infrastructure."
                author="James Rodriguez"
                role="Head of AI, TechVault"
                avatar="JR"
                rating={5}
              />
            </div>
          </div>
        </section>

        {/* ════════════════════════════════════════════════
           PRICING
           ════════════════════════════════════════════════ */}
        <section id="pricing" className="py-24 md:py-32">
          <div className="section-container">
            <div className="max-w-2xl mx-auto text-center mb-16">
              <div className="label mb-4" style={{ color: "var(--text-accent)" }}>Pricing</div>
              <h2 className="text-2xl sm:text-3xl font-bold mb-4">
                Plans for every{" "}
                <span className="text-gradient">scale</span>
              </h2>
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                From startups to enterprises. Self-hosted and fully under your control.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-4xl mx-auto">
              <PricingCard
                name="Starter"
                desc="For small teams exploring GraphRAG"
                price="$0"
                features={[
                  "Up to 1,000 queries/month",
                  "5 document uploads",
                  "Basic hybrid retrieval",
                  "Community support",
                  "Self-hosted",
                ]}
                cta="Get Started"
              />
              <PricingCard
                name="Pro"
                desc="For growing teams with production needs"
                price="$199"
                popular={true}
                features={[
                  "Up to 50,000 queries/month",
                  "Unlimited document uploads",
                  "Full multi-agent pipeline",
                  "Self-healing & hallucination detection",
                  "Knowledge graph integration",
                  "Priority support",
                  "Audit logging & RBAC",
                ]}
                cta="Start Free Trial"
              />
              <PricingCard
                name="Enterprise"
                desc="For organizations at scale"
                price="Custom"
                features={[
                  "Unlimited queries",
                  "Custom agent configuration",
                  "SSO & SAML integration",
                  "Dedicated infrastructure",
                  "24/7 premium support",
                  "Custom SLAs",
                  "On-premise deployment",
                  "SOC 2 compliance",
                ]}
                cta="Contact Sales"
              />
            </div>
          </div>
        </section>

        {/* ════════════════════════════════════════════════
           FAQ
           ════════════════════════════════════════════════ */}
        <section className="py-24 md:py-32">
          <div className="section-container">
            <div className="max-w-2xl mx-auto">
              <div className="text-center mb-12">
                <div className="label mb-4" style={{ color: "var(--text-accent)" }}>FAQ</div>
                <h2 className="text-2xl sm:text-3xl font-bold mb-4">
                  Frequently asked{" "}
                  <span className="text-gradient">questions</span>
                </h2>
              </div>

              <div className="space-y-2">
                <FAQItem
                  question="What is Nexus Core and how does it work?"
                  answer="Nexus Core is a multi-agent RAG (Retrieval-Augmented Generation) platform that uses a pipeline of specialized agents to retrieve, generate, verify, and automatically correct answers. It detects hallucinations and self-heals without human intervention."
                />
                <FAQItem
                  question="How does the self-healing mechanism work?"
                  answer="When the Critic Agent detects an unverifiable claim in the generated answer, the Healer Agent automatically rewrites the query, re-retrieves from the knowledge base, and regenerates the answer. This loop continues until all claims are verified or a maximum retry threshold is reached."
                />
                <FAQItem
                  question="What data sources does Nexus Core support?"
                  answer="Nexus Core supports PDF, DOCX, TXT, and Markdown files. Documents are processed through a chunking pipeline and indexed in ChromaDB (vector store), Neo4j (knowledge graph), and BM25 (keyword index) for hybrid retrieval."
                />
                <FAQItem
                  question="Is Nexus Core self-hosted?"
                  answer="Yes, Nexus Core is designed to be self-hosted in your infrastructure. We provide Docker Compose and Kubernetes configurations for easy deployment. Enterprise plans include on-premise deployment options."
                />
                <FAQItem
                  question="How does hallucination detection work?"
                  answer="The Critic Agent extracts every factual claim from the generated answer and verifies each one against the retrieved context using groundedness scoring. Claims are classified as verified, unsupported, or contradicted, and the overall confidence score is calculated."
                />
              </div>
            </div>
          </div>
        </section>

        {/* ════════════════════════════════════════════════
           CTA
           ════════════════════════════════════════════════ */}
        <section className="py-24 md:py-32">
          <div className="section-container">
            <div
              className="rounded-2xl p-10 sm:p-16 text-center relative overflow-hidden"
              style={{
                background: "linear-gradient(135deg, rgba(99,102,241,0.06), rgba(139,92,246,0.04))",
                border: "1px solid rgba(99,102,241,0.12)",
              }}
            >
              <div className="hero-orb" style={{
                width: "400px", height: "400px",
                background: "radial-gradient(circle, rgba(99,102,241,0.08), transparent)",
                top: "-150px", right: "-150px",
                animation: "orbMove 15s ease-in-out infinite",
              }} />

              <div className="relative z-10">
                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[9px] font-medium mb-6" style={{ background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.15)", color: "var(--text-accent)" }}>
                  <Rocket size={10} />
                  Get started in minutes
                </div>
                <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold mb-4 leading-tight">
                  Ready to build{" "}
                  <span className="text-gradient">trustworthy</span> AI?
                </h2>
                <p className="text-sm mb-8 max-w-md mx-auto" style={{ color: "var(--text-secondary)" }}>
                  Deploy Nexus Core in your infrastructure. Self-hosted, 
                  secure, and fully observable. Start with our free tier.
                </p>
                <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                  <a
                    href="/dashboard"
                    className="btn-primary px-8 py-3.5 text-sm inline-flex items-center gap-2"
                    style={{ borderRadius: "12px", fontSize: "14px" }}
                  >
                    Launch Dashboard <ArrowRight size={14} />
                  </a>
                  <a
                    href="/docs"
                    className="btn-outline px-8 py-3.5 text-sm inline-flex items-center gap-2"
                    style={{ borderRadius: "12px", fontSize: "14px" }}
                  >
                    <BookOpen size={12} /> Read the Docs
                  </a>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </>
  );
}