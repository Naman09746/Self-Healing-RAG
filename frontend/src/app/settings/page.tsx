"use client";

import { useState, useEffect } from "react";
import {
  ArrowLeft,
  Settings,
  User,
  Key,
  Database,
  Cpu,
  Palette,
  Save,
  CheckCircle,
  Loader2,
  Eye,
  EyeOff,
  RefreshCw,
  Moon,
  Sun,
  Activity,
  AlertCircle,
  Sliders,
} from "lucide-react";
import Link from "next/link";
import { useToast } from "@/components/Toast";

/* ─── Setting Section ──────────────────────────────────── */
function SettingSection({
  icon,
  title,
  desc,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl p-5 space-y-4 bg-white border border-slate-200/90 shadow-xs">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 bg-blue-50 border border-blue-200/60 text-blue-600">
          {icon}
        </div>
        <div>
          <h3 className="text-sm font-bold text-slate-900">{title}</h3>
          <p className="text-xs text-slate-500 mt-0.5">{desc}</p>
        </div>
      </div>
      <div className="pl-0 sm:pl-11">{children}</div>
    </div>
  );
}

/* ─── Toggle Switch ─────────────────────────────────────── */
function Toggle({
  checked,
  onChange,
  label,
  sublabel,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  sublabel?: string;
}) {
  return (
    <div className="flex items-center justify-between py-1">
      <div>
        <div className="text-xs font-semibold text-slate-800">{label}</div>
        {sublabel && <div className="text-[11px] text-slate-400">{sublabel}</div>}
      </div>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`w-9 h-5 rounded-full relative transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500/30 ${
          checked ? "bg-blue-600" : "bg-slate-200"
        }`}
      >
        <span
          className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all duration-200 shadow-xs ${
            checked ? "left-[18px]" : "left-0.5"
          }`}
        />
      </button>
    </div>
  );
}

/* ─── Main Settings Page ───────────────────────────────── */
export default function SettingsPage() {
  const { toast } = useToast();
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<string | null>(null);
  const [showApiKey, setShowApiKey] = useState(false);

  // Form state with persistent defaults
  const [form, setForm] = useState({
    displayName: "Platform Admin",
    email: "admin@self-healing-rag.local",
    apiEndpoint: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
    apiKey: "sk-live-production-jwt",
    theme: "light",
    streamingEnabled: true,
    fastFailEnabled: true,
    fastPathCritic: true,
    llmModel: "llama3.2:1b",
    embeddingModel: "nomic-embed-text",
    maxRetries: "1",
    relevanceThreshold: "0.50",
    topK: "5",
    cacheHitOptimization: true,
  });

  useEffect(() => {
    try {
      const stored = localStorage.getItem("nexus_settings");
      if (stored) {
        setForm((prev) => ({ ...prev, ...JSON.parse(stored) }));
      }
    } catch {
      // ignore
    }
  }, []);

  const handleSave = () => {
    setSaving(true);
    try {
      localStorage.setItem("nexus_settings", JSON.stringify(form));
      setSaved(true);
      toast.success("Runtime configuration saved successfully!");
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      toast.error("Failed to persist settings: " + (e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setTestingConnection(true);
    setConnectionStatus(null);
    try {
      const baseUrl = form.apiEndpoint.replace(/\/api\/v1\/?$/, "");
      const start = Date.now();
      const res = await fetch(`${baseUrl}/health`);
      const latency = Date.now() - start;
      if (res.ok) {
        setConnectionStatus(`Connected (${latency}ms) — All services operational`);
        toast.success(`Backend ping succeeded in ${latency}ms`);
      } else {
        setConnectionStatus(`Backend responded with error: ${res.status}`);
        toast.error(`Backend returned HTTP ${res.status}`);
      }
    } catch (err) {
      setConnectionStatus("Failed to reach endpoint. Ensure backend server is running.");
      toast.error("Connection failed: backend unreachable");
    } finally {
      setTestingConnection(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 selection:bg-blue-100">
      {/* Header */}
      <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-md border-b border-slate-200/90 h-14 px-5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard"
            className="w-8 h-8 rounded-lg border border-slate-200 flex items-center justify-center text-slate-500 hover:text-slate-800 hover:bg-slate-50 transition-colors"
            title="Return to Dashboard"
          >
            <ArrowLeft size={15} />
          </Link>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-blue-50 text-blue-600 flex items-center justify-center">
              <Settings size={14} />
            </div>
            <span className="text-sm font-bold text-slate-900">System Configuration</span>
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white text-xs font-semibold shadow-xs transition-all disabled:opacity-50"
        >
          {saving ? (
            <>
              <Loader2 size={13} className="animate-spin" />
              <span>Saving…</span>
            </>
          ) : saved ? (
            <>
              <CheckCircle size={13} className="text-emerald-300" />
              <span>Saved</span>
            </>
          ) : (
            <>
              <Save size={13} />
              <span>Save Configuration</span>
            </>
          )}
        </button>
      </header>

      {/* Main Content Stage */}
      <main className="max-w-3xl mx-auto p-5 sm:p-6 space-y-4">
        {/* Profile Card */}
        <SettingSection
          icon={<User size={15} />}
          title="Account & Identity"
          desc="Workspace operator credentials"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-700 mb-1 block">
                Display Name
              </label>
              <input
                type="text"
                value={form.displayName}
                onChange={(e) => setForm({ ...form, displayName: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-700 mb-1 block">
                Operator Email
              </label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
          </div>
        </SettingSection>

        {/* API & Backend Connectivity */}
        <SettingSection
          icon={<Key size={15} />}
          title="Backend API & Gateway"
          desc="Endpoint discovery and health status validation"
        >
          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold text-slate-700 mb-1 block">
                FastAPI Base Route
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={form.apiEndpoint}
                  onChange={(e) => setForm({ ...form, apiEndpoint: e.target.value })}
                  className="flex-1 px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 text-xs font-mono text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={handleTestConnection}
                  disabled={testingConnection}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-colors disabled:opacity-50 shrink-0"
                >
                  {testingConnection ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <Activity size={13} className="text-blue-600" />
                  )}
                  <span>Test Ping</span>
                </button>
              </div>
              {connectionStatus && (
                <div
                  className={`mt-2 p-2 rounded-lg text-xs font-medium ${
                    connectionStatus.includes("Connected")
                      ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                      : "bg-rose-50 text-rose-700 border border-rose-200"
                  }`}
                >
                  {connectionStatus}
                </div>
              )}
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 mb-1 block">
                Bearer Secret / API Key
              </label>
              <div className="relative">
                <input
                  type={showApiKey ? "text" : "password"}
                  value={form.apiKey}
                  onChange={(e) => setForm({ ...form, apiKey: e.target.value })}
                  className="w-full px-3 pr-10 py-2 rounded-lg bg-slate-50 border border-slate-200 text-xs font-mono text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showApiKey ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>
          </div>
        </SettingSection>

        {/* Pipeline & Latency Optimization Controls */}
        <SettingSection
          icon={<Sliders size={15} />}
          title="Latency & Self-Healing Budget"
          desc="Fine-tune early exits, critic fast-paths, and retry budgets"
        >
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-700 mb-1 block">
                Max Self-Heal Retries
              </label>
              <select
                value={form.maxRetries}
                onChange={(e) => setForm({ ...form, maxRetries: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              >
                <option value="1">1 (Recommended — bounded latency)</option>
                <option value="2">2 (Deep analysis mode)</option>
                <option value="0">0 (Strict single-shot pass)</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 mb-1 block">
                Fast-Fail Threshold
              </label>
              <input
                type="number"
                step="0.05"
                min="0.1"
                max="0.9"
                value={form.relevanceThreshold}
                onChange={(e) => setForm({ ...form, relevanceThreshold: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
              <span className="text-[10px] text-slate-400 mt-0.5 block">Exits ~200ms if below</span>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 mb-1 block">
                Top-K Chunks
              </label>
              <select
                value={form.topK}
                onChange={(e) => setForm({ ...form, topK: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              >
                <option value="3">3 (Low latency)</option>
                <option value="5">5 (Balanced default)</option>
                <option value="10">10 (Exhaustive search)</option>
              </select>
            </div>
          </div>

          <div className="pt-3 border-t border-slate-100 space-y-2">
            <Toggle
              checked={form.fastFailEnabled}
              onChange={(v) => setForm({ ...form, fastFailEnabled: v })}
              label="Knowledge-Absence Fast-Fail"
              sublabel="Immediately return early when 0 chunks meet relevance threshold (~200ms)"
            />
            <Toggle
              checked={form.fastPathCritic}
              onChange={(v) => setForm({ ...form, fastPathCritic: v })}
              label="Single-Pass Critic Fast-Path"
              sublabel="Collapse 3 LLM verification calls into 1 pass for simple queries (<0.3 complexity)"
            />
            <Toggle
              checked={form.streamingEnabled}
              onChange={(v) => setForm({ ...form, streamingEnabled: v })}
              label="SSE Token & Phase Streaming"
              sublabel="Stream incremental tokens and multi-agent phase state in real-time"
            />
          </div>
        </SettingSection>

        {/* Model Selection */}
        <SettingSection
          icon={<Cpu size={15} />}
          title="Inference Models (Ollama)"
          desc="Select the active LLM generator and dense embedding encoder"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-700 mb-1 block">
                LLM Generator
              </label>
              <select
                value={form.llmModel}
                onChange={(e) => setForm({ ...form, llmModel: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              >
                <option value="llama-3.3-70b-versatile">Llama 3.3 70B (Groq Cloud — Ultra-Fast)</option>
                <option value="llama-3.1-8b-instant">Llama 3.1 8B (Groq Cloud — Low Latency)</option>
                <option value="llama3.2:1b">Llama 3.2 1B (Ollama Local / Lightweight)</option>
                <option value="mistral:7b">Mistral 7B</option>
                <option value="qwen2.5:7b">Qwen 2.5 7B</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 mb-1 block">
                Embedding Model
              </label>
              <select
                value={form.embeddingModel}
                onChange={(e) => setForm({ ...form, embeddingModel: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              >
                <option value="nomic-embed-text">Nomic Embed Text (8192 ctx)</option>
                <option value="all-minilm">All MiniLM L6 v2 (Fast)</option>
                <option value="mxbai-embed-large">MXBAI Embed Large</option>
              </select>
            </div>
          </div>
        </SettingSection>
      </main>
    </div>
  );
}
