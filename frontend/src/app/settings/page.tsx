"use client";

import { useState, useEffect } from "react";
import {
  ArrowLeft,
  Settings,
  User,
  Shield,
  Bell,
  Globe,
  Key,
  Database,
  Cpu,
  Palette,
  ChevronRight,
  Save,
  CheckCircle,
  Loader2,
  Eye,
  EyeOff,
  RefreshCw,
  Moon,
  Sun,
} from "lucide-react";
import Link from "next/link";

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
    <div
      className="rounded-xl p-5 space-y-4"
      style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)" }}
    >
      <div className="flex items-start gap-3">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: "rgba(99,102,241,0.1)" }}
        >
          {icon}
        </div>
        <div>
          <h3 className="text-sm font-semibold" style={{ color: "#e8e8ed" }}>{title}</h3>
          <p className="text-[11px] mt-0.5" style={{ color: "#525266" }}>{desc}</p>
        </div>
      </div>
      <div className="pl-11">
        {children}
      </div>
    </div>
  );
}

/* ─── Toggle Switch ─────────────────────────────────────── */
function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="flex items-center justify-between cursor-pointer group">
      <span className="text-xs" style={{ color: "#8b8b9e" }}>{label}</span>
      <div
        onClick={() => onChange(!checked)}
        className={`w-9 h-5 rounded-full relative transition-all duration-200 ${
          checked ? "bg-indigo-500" : "bg-white/[0.08]"
        }`}
      >
        <div
          className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all duration-200 shadow-sm ${
            checked ? "left-[18px]" : "left-0.5"
          }`}
        />
      </div>
    </label>
  );
}

/* ─── Main Settings Page ───────────────────────────────── */
export default function SettingsPage() {
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);

  // Form state
  const [form, setForm] = useState({
    displayName: "Admin User",
    email: "admin@nexus-core.io",
    apiEndpoint: "http://localhost:8000/api/v1",
    apiKey: "sk-..." as string,
    theme: "dark",
    streamingEnabled: true,
    pipelineNotifications: true,
    hallucinationAlerts: true,
    llmModel: "mistral:7b",
    embeddingModel: "nomic-embed-text",
    maxRetries: "3",
    confidenceThreshold: "0.7",
    topK: "5",
    autoClearCache: false,
  });

  const handleSave = async () => {
    setSaving(true);
    // Simulate API call
    await new Promise((r) => setTimeout(r, 1000));
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div className="min-h-screen" style={{ background: "#08080c" }}>
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 h-14"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
      >
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard"
            className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-white/5 transition-colors"
            style={{ color: "#525266" }}
          >
            <ArrowLeft size={14} />
          </Link>
          <Settings size={14} style={{ color: "#a5b4fc" }} />
          <span className="text-sm font-semibold" style={{ color: "#e8e8ed" }}>
            Settings
          </span>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className={`btn text-xs ${saved ? "btn-accent" : "btn-primary"}`}
        >
          {saving ? (
            <>
              <Loader2 size={12} className="animate-spin" /> Saving...
            </>
          ) : saved ? (
            <>
              <CheckCircle size={12} /> Saved
            </>
          ) : (
            <>
              <Save size={12} /> Save Changes
            </>
          )}
        </button>
      </div>

      {/* Content */}
      <div className="max-w-3xl mx-auto p-5 space-y-4">
        {/* ── Profile ── */}
        <SettingSection
          icon={<User size={15} style={{ color: "#a5b4fc" }} />}
          title="Profile"
          desc="Your account information"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block" style={{ color: "#525266" }}>
                Display Name
              </label>
              <input
                type="text"
                value={form.displayName}
                onChange={(e) => setForm({ ...form, displayName: e.target.value })}
                className="input text-xs"
                style={{ background: "rgba(255,255,255,0.03)" }}
              />
            </div>
            <div>
              <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block" style={{ color: "#525266" }}>
                Email
              </label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="input text-xs"
                style={{ background: "rgba(255,255,255,0.03)" }}
              />
            </div>
          </div>
        </SettingSection>

        {/* ── API Configuration ── */}
        <SettingSection
          icon={<Key size={15} style={{ color: "#a5b4fc" }} />}
          title="API Configuration"
          desc="Connection settings for the backend"
        >
          <div className="space-y-3">
            <div>
              <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block" style={{ color: "#525266" }}>
                API Endpoint
              </label>
              <input
                type="text"
                value={form.apiEndpoint}
                onChange={(e) => setForm({ ...form, apiEndpoint: e.target.value })}
                className="input text-xs font-mono"
                style={{ background: "rgba(255,255,255,0.03)" }}
              />
            </div>
            <div>
              <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block" style={{ color: "#525266" }}>
                API Key
              </label>
              <div className="relative">
                <input
                  type={showApiKey ? "text" : "password"}
                  value={form.apiKey}
                  onChange={(e) => setForm({ ...form, apiKey: e.target.value })}
                  className="input text-xs font-mono pr-9"
                  style={{ background: "rgba(255,255,255,0.03)" }}
                />
                <button
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2"
                  style={{ color: "#525266" }}
                >
                  {showApiKey ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>
          </div>
        </SettingSection>

        {/* ── LLM Configuration ── */}
        <SettingSection
          icon={<Cpu size={15} style={{ color: "#a5b4fc" }} />}
          title="LLM Configuration"
          desc="Model and generation settings"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block" style={{ color: "#525266" }}>
                LLM Model
              </label>
              <select
                value={form.llmModel}
                onChange={(e) => setForm({ ...form, llmModel: e.target.value })}
                className="input text-xs"
                style={{ background: "rgba(255,255,255,0.03)" }}
              >
                <option value="mistral:7b">Mistral 7B</option>
                <option value="llama3:8b">Llama 3 8B</option>
                <option value="llama3:70b">Llama 3 70B</option>
                <option value="mixtral:8x7b">Mixtral 8x7B</option>
                <option value="phi3:mini">Phi-3 Mini</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block" style={{ color: "#525266" }}>
                Embedding Model
              </label>
              <select
                value={form.embeddingModel}
                onChange={(e) => setForm({ ...form, embeddingModel: e.target.value })}
                className="input text-xs"
                style={{ background: "rgba(255,255,255,0.03)" }}
              >
                <option value="nomic-embed-text">Nomic Embed Text</option>
                <option value="all-minilm">All MiniLM L6 v2</option>
                <option value="mxbai-embed-large">MXBAI Embed Large</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block" style={{ color: "#525266" }}>
                Max Retries (Self-Heal)
              </label>
              <input
                type="number"
                value={form.maxRetries}
                onChange={(e) => setForm({ ...form, maxRetries: e.target.value })}
                className="input text-xs"
                min={0}
                max={10}
                style={{ background: "rgba(255,255,255,0.03)" }}
              />
            </div>
            <div>
              <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block" style={{ color: "#525266" }}>
                Confidence Threshold
              </label>
              <input
                type="number"
                value={form.confidenceThreshold}
                onChange={(e) => setForm({ ...form, confidenceThreshold: e.target.value })}
                className="input text-xs"
                min={0}
                max={1}
                step={0.05}
                style={{ background: "rgba(255,255,255,0.03)" }}
              />
            </div>
            <div>
              <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block" style={{ color: "#525266" }}>
                Top-K Retrieval
              </label>
              <select
                value={form.topK}
                onChange={(e) => setForm({ ...form, topK: e.target.value })}
                className="input text-xs"
                style={{ background: "rgba(255,255,255,0.03)" }}
              >
                <option value="3">3 (Simple queries)</option>
                <option value="5">5 (Medium queries)</option>
                <option value="10">10 (Complex queries)</option>
                <option value="auto">Auto (Adaptive)</option>
              </select>
            </div>
          </div>
        </SettingSection>

        {/* ── Preferences ── */}
        <SettingSection
          icon={<Palette size={15} style={{ color: "#a5b4fc" }} />}
          title="Preferences"
          desc="Appearance and behavior"
        >
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all" style={{ border: form.theme === "dark" ? "1px solid rgba(99,102,241,0.3)" : "1px solid rgba(255,255,255,0.06)", background: form.theme === "dark" ? "rgba(99,102,241,0.08)" : "transparent" }} onClick={() => setForm({ ...form, theme: "dark" })}>
                <Moon size={14} style={{ color: form.theme === "dark" ? "#a5b4fc" : "#525266" }} />
                <span className="text-xs" style={{ color: form.theme === "dark" ? "#a5b4fc" : "#8b8b9e" }}>Dark</span>
              </div>
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all" style={{ border: form.theme === "light" ? "1px solid rgba(99,102,241,0.3)" : "1px solid rgba(255,255,255,0.06)", background: form.theme === "light" ? "rgba(99,102,241,0.08)" : "transparent" }} onClick={() => setForm({ ...form, theme: "light" })}>
                <Sun size={14} style={{ color: form.theme === "light" ? "#a5b4fc" : "#525266" }} />
                <span className="text-xs" style={{ color: form.theme === "light" ? "#a5b4fc" : "#8b8b9e" }}>Light</span>
              </div>
            </div>
            <Toggle checked={form.streamingEnabled} onChange={(v) => setForm({ ...form, streamingEnabled: v })} label="Enable streaming responses" />
            <Toggle checked={form.autoClearCache} onChange={(v) => setForm({ ...form, autoClearCache: v })} label="Auto-clear query cache on startup" />
          </div>
        </SettingSection>

        {/* ── Notifications ── */}
        <SettingSection
          icon={<Bell size={15} style={{ color: "#a5b4fc" }} />}
          title="Notifications"
          desc="Alert preferences"
        >
          <div className="space-y-3">
            <Toggle checked={form.pipelineNotifications} onChange={(v) => setForm({ ...form, pipelineNotifications: v })} label="Pipeline phase completion notifications" />
            <Toggle checked={form.hallucinationAlerts} onChange={(v) => setForm({ ...form, hallucinationAlerts: v })} label="Hallucination detection alerts" />
          </div>
        </SettingSection>

        {/* ── Danger Zone ── */}
        <div
          className="rounded-xl p-5 space-y-4"
          style={{ border: "1px solid rgba(239,68,68,0.2)", background: "rgba(239,68,68,0.03)" }}
        >
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: "rgba(239,68,68,0.1)" }}>
              <Database size={15} style={{ color: "#ef4444" }} />
            </div>
            <div>
              <h3 className="text-sm font-semibold" style={{ color: "#ef4444" }}>Danger Zone</h3>
              <p className="text-[11px] mt-0.5" style={{ color: "#8b8b9e" }}>
                Destructive actions that cannot be undone
              </p>
            </div>
          </div>
          <div className="pl-11 space-y-3">
            <button
              className="btn text-xs"
              style={{ border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444", background: "transparent" }}
              onClick={() => {
                if (confirm("Clear all indexed documents and cached data?")) {
                  // Clear cache action
                }
              }}
            >
              <RefreshCw size={12} /> Clear Query Cache
            </button>
            <button
              className="btn text-xs"
              style={{ border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444", background: "transparent" }}
              onClick={() => {
                if (confirm("Are you sure you want to re-index all documents?")) {
                  // Re-index action
                }
              }}
            >
              <Database size={12} /> Re-index All Documents
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
