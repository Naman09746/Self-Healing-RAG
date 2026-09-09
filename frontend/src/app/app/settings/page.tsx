"use client";

import { useState, useEffect } from "react";
import {
  Settings,
  User,
  Key,
  Database,
  Cpu,
  Save,
  CheckCircle,
  Loader2,
  Eye,
  EyeOff,
  RefreshCw,
  Sliders,
} from "lucide-react";
import { useToast } from "@/components/Toast";

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
    <div className="rounded-xl p-5 space-y-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800">
          {icon}
        </div>
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">{title}</h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{desc}</p>
        </div>
      </div>
      <div className="pl-0 sm:pl-11">{children}</div>
    </div>
  );
}

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
        <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">{label}</div>
        {sublabel && <div className="text-[11px] text-slate-400 dark:text-slate-500">{sublabel}</div>}
      </div>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`w-9 h-5 rounded-full relative transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500/30 cursor-pointer ${
          checked ? "bg-blue-600" : "bg-slate-200 dark:bg-slate-700"
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

export default function SettingsPage() {
  const { toast } = useToast();
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<string | null>(null);
  const [showApiKey, setShowApiKey] = useState(false);

  const [form, setForm] = useState({
    displayName: "Platform Admin",
    email: "admin@self-healing-rag.local",
    apiEndpoint: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
    apiKey: "sk-live-production-jwt",
    streamingEnabled: true,
    fastFailEnabled: true,
    fastPathCritic: true,
    llmModel: "llama3.3-70b-versatile",
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
      if (form.apiEndpoint) {
        localStorage.setItem("nexus_api_endpoint", form.apiEndpoint.trim());
      }
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
    } catch {
      setConnectionStatus("Failed to reach endpoint. Ensure backend server is running.");
      toast.error("Connection failed: backend unreachable");
    } finally {
      setTestingConnection(false);
    }
  };

  return (
    <div className="p-4 sm:p-6 max-w-4xl w-full mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            System Configuration &amp; Settings
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Manage LLM model routing, vector thresholds, guardrail retries, and backend API endpoints.
          </p>
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white text-xs font-semibold shadow-xs transition-all disabled:opacity-50 cursor-pointer self-start sm:self-auto"
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
              <span>Save Changes</span>
            </>
          )}
        </button>
      </div>

      <div className="space-y-4">
        {/* Profile Card */}
        <SettingSection
          icon={<User size={15} />}
          title="Account &amp; Identity"
          desc="Workspace operator credentials"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                Display Name
              </label>
              <input
                type="text"
                value={form.displayName}
                onChange={(e) => setForm({ ...form, displayName: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                Operator Email
              </label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
          </div>
        </SettingSection>

        {/* API & Cluster Connectivity */}
        <SettingSection
          icon={<Key size={15} />}
          title="Backend API Connectivity"
          desc="FastAPI / Render endpoint orchestration"
        >
          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                API Base URL
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={form.apiEndpoint}
                  onChange={(e) => setForm({ ...form, apiEndpoint: e.target.value })}
                  placeholder="https://...onrender.com/api/v1"
                  className="flex-1 px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-mono text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
                <button
                  onClick={handleTestConnection}
                  disabled={testingConnection}
                  className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-xs text-slate-700 dark:text-slate-300 font-medium transition-colors flex items-center gap-1.5 shrink-0"
                >
                  {testingConnection ? (
                    <Loader2 size={13} className="animate-spin text-blue-600" />
                  ) : (
                    <RefreshCw size={13} />
                  )}
                  <span>Test Connection</span>
                </button>
              </div>
              {connectionStatus && (
                <p className="text-[11px] mt-1.5 font-mono text-slate-500 dark:text-slate-400">
                  {connectionStatus}
                </p>
              )}
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                Authorization Token (JWT)
              </label>
              <div className="relative">
                <input
                  type={showApiKey ? "text" : "password"}
                  value={form.apiKey}
                  onChange={(e) => setForm({ ...form, apiKey: e.target.value })}
                  className="w-full px-3 py-2 pr-10 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-mono text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                  aria-label={showApiKey ? "Hide key" : "Show key"}
                >
                  {showApiKey ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>
          </div>
        </SettingSection>

        {/* Model Architecture */}
        <SettingSection
          icon={<Cpu size={15} />}
          title="LLM &amp; Embeddings Routing"
          desc="Models utilized for intake, generation, and critic agents"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                Primary LLM Model
              </label>
              <select
                value={form.llmModel}
                onChange={(e) => setForm({ ...form, llmModel: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              >
                <option value="llama-3.3-70b-versatile">llama-3.3-70b-versatile (Groq Cloud)</option>
                <option value="llama3.2:1b">llama3.2:1b (Local Ollama)</option>
                <option value="mistral:7b">mistral:7b (Local Ollama)</option>
                <option value="gpt-4o-mini">gpt-4o-mini (OpenAI API)</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                Embedding Model
              </label>
              <select
                value={form.embeddingModel}
                onChange={(e) => setForm({ ...form, embeddingModel: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              >
                <option value="nomic-embed-text">nomic-embed-text (Ollama / Local)</option>
                <option value="text-embedding-3-small">text-embedding-3-small (OpenAI)</option>
                <option value="all-MiniLM-L6-v2">all-MiniLM-L6-v2 (HuggingFace)</option>
              </select>
            </div>
          </div>
        </SettingSection>

        {/* Retrieval & Self-Healing Parameters */}
        <SettingSection
          icon={<Sliders size={15} />}
          title="Retrieval &amp; Self-Healing Guardrails"
          desc="Fine-tune thresholds, top-k, and automated query rewriting"
        >
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                Relevance Threshold
              </label>
              <input
                type="number"
                step="0.05"
                min="0.1"
                max="0.95"
                value={form.relevanceThreshold}
                onChange={(e) => setForm({ ...form, relevanceThreshold: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                Retriever Top-K
              </label>
              <input
                type="number"
                min="1"
                max="20"
                value={form.topK}
                onChange={(e) => setForm({ ...form, topK: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 block">
                Max Self-Heal Retries
              </label>
              <input
                type="number"
                min="0"
                max="3"
                value={form.maxRetries}
                onChange={(e) => setForm({ ...form, maxRetries: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
          </div>

          <div className="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800">
            <Toggle
              checked={form.streamingEnabled}
              onChange={(v) => setForm({ ...form, streamingEnabled: v })}
              label="SSE Real-Time Token Streaming"
              sublabel="Stream generated answer tokens in real-time as they are synthesized."
            />
            <Toggle
              checked={form.fastPathCritic}
              onChange={(v) => setForm({ ...form, fastPathCritic: v })}
              label="Critic Fast-Path Optimization"
              sublabel="Skip full claim decomposition for simple queries with high similarity confidence."
            />
            <Toggle
              checked={form.fastFailEnabled}
              onChange={(v) => setForm({ ...form, fastFailEnabled: v })}
              label="Fast-Fail Retrieval Protection"
              sublabel="Immediately abort and rewrite query if initial chunk score is below threshold."
            />
          </div>
        </SettingSection>
      </div>
    </div>
  );
}
