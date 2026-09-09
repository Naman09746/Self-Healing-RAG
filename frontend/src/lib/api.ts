/**
 * API Client — Self-Healing RAG
 *
 * Typed client for all backend API interactions.
 * Provides auth token management, request/response interceptors,
 * and real-time SSE streaming for pipeline results.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

// ─── Token Management ─────────────────────────────────────

let _accessToken: string | null = null;
let _refreshToken: string | null = null;

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return _accessToken || localStorage.getItem("rag_access_token");
}

export function setTokens(access: string, refresh?: string): void {
  _accessToken = access;
  _refreshToken = refresh || null;
  localStorage.setItem("rag_access_token", access);
  if (refresh) localStorage.setItem("rag_refresh_token", refresh);
}

export function clearTokens(): void {
  _accessToken = null;
  _refreshToken = null;
  localStorage.removeItem("rag_access_token");
  localStorage.removeItem("rag_refresh_token");
}

export function isAuthenticated(): boolean {
  return !!getAccessToken();
}

// ─── Types ─────────────────────────────────────────────────

export interface AuthResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
}

export interface UserProfile {
  email: string;
  role: "admin" | "editor" | "viewer" | "auditor";
  tenant_id: string;
  user_uuid: string;
}

export interface ServiceHealth {
  status: "healthy" | "degraded" | "unhealthy" | "uninitialized" | "disabled_or_unavailable";
  latency_ms?: number;
  error?: string;
}

export interface HealthStatus {
  status: string;
  version: string;
  services: Record<string, ServiceHealth | string>;
}

export interface QueryRequest {
  query: string;
  session_id?: string;
  tenant_id?: string;
  stream?: boolean;
}

export interface RetrievedChunk {
  chunk_id: string;
  content: string;
  score: number;
  source: string;
}

export interface QueryResponse {
  answer: string;
  session_id: string;
  query?: string;
  phase_timings?: Record<string, number>;
  sources?: RetrievedChunk[];
  chunks_retrieved?: number;
  status?: string;
  grounding_score: number;
  is_hallucinated?: boolean;
  healing_actions?: string[];
  verification_mode?: string;
  complexity_score?: number;
  retry_count?: number;
}

export interface DocumentInfo {
  id: string;
  filename: string;
  status: "indexed" | "processing" | "failed";
  pages: number;
  chunks: number;
  file_size: number;
  created_at: string;
  document_type: string;
}

export interface IngestionResponse {
  document_id: string;
  filename: string;
  status: string;
  chunks_count: number;
}

export interface MetricsSnapshot {
  queries_total: number;
  hallucinations_total: number;
  healings_total: number;
  avg_grounding_score: number;
  avg_latency_ms: number;
  cache_hit_rate: number;
  active_queries: number;
  grounding_trend?: number[];
  latency_trend?: number[];
  phase_breakdown_ms?: Record<string, number>;
}


export interface EvaluationResult {
  faithfulness: number;
  answer_relevancy: number;
  context_precision: number;
  context_recall: number;
  composite_score: number;
}

// ─── HTTP Client ───────────────────────────────────────────

class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  opts?: { skipAuth?: boolean; timeout?: number }
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (!opts?.skipAuth) {
    const token = getAccessToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  const controller = new AbortController();
  const timeout = opts?.timeout || 30000;
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const res = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new ApiError(
        res.status,
        errBody.code || "UNKNOWN",
        errBody.message || res.statusText,
        errBody
      );
    }

    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if ((err as Error).name === "AbortError") {
      throw new ApiError(408, "TIMEOUT", `Request timed out after ${timeout}ms`);
    }
    throw new ApiError(0, "NETWORK", (err as Error).message);
  } finally {
    clearTimeout(timeoutId);
  }
}

// ─── Auth API ──────────────────────────────────────────────

export const auth = {
  login: (email: string, password: string) =>
    request<AuthResponse>("POST", "/auth/login", { email, password }, { skipAuth: true }),

  signup: (email: string, password: string, name?: string) =>
    request<AuthResponse>("POST", "/auth/signup", { email, password, name }, { skipAuth: true }),

  refresh: (refreshToken: string) =>
    request<AuthResponse>("POST", "/auth/refresh", { refresh_token: refreshToken }, { skipAuth: true }),

  profile: () => request<UserProfile>("GET", "/auth/me"),
};

// ─── Query API ─────────────────────────────────────────────

export const query = {
  ask: (req: QueryRequest) =>
    request<QueryResponse>("POST", "/query", req, { timeout: 120000 }),

  askStream: (req: QueryRequest, callbacks: {
    onToken?: (token: string) => void;
    onPhase?: (phase: string) => void;
    onComplete?: (result: QueryResponse) => void;
    onError?: (err: Error) => void;
  }): AbortController => {
    const controller = new AbortController();
    const token = getAccessToken();

    fetch(`${BASE_URL}/query/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(req),
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ message: res.statusText }));
          throw new Error(err.message);
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              const eventType = line.slice(7).trim();
              // Next line should be data:
              continue;
            }
            if (line.startsWith("data: ")) {
              const data = line.slice(6).trim();
              try {
                const parsed = JSON.parse(data);
                if (parsed.phase && callbacks.onPhase) {
                  callbacks.onPhase(parsed.phase);
                }
                if (parsed.token && callbacks.onToken) {
                  callbacks.onToken(parsed.token);
                }
                if (parsed.answer && callbacks.onComplete) {
                  callbacks.onComplete(parsed);
                }
              } catch {
                // Partial JSON — skip
              }
            }
          }
        }
      })
      .catch((err) => {
        if (err.name === "AbortError") return;
        callbacks.onError?.(err);
      });

    return controller;
  },
};

// ─── Documents API ─────────────────────────────────────────

export const documents = {
  list: () => request<DocumentInfo[]>("GET", "/documents"),

  upload: async (file: File): Promise<IngestionResponse> => {
    const formData = new FormData();
    formData.append("file", file);

    const token = getAccessToken();
    const res = await fetch(`${BASE_URL}/ingest`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(res.status, err.code || "UPLOAD_FAILED", err.message || res.statusText);
    }
    return res.json();
  },

  delete: (id: string) => request<void>("DELETE", `/documents/${id}`),
};

// ─── Health API ────────────────────────────────────────────

export const health = {
  check: () =>
    request<HealthStatus>("GET", "/health", undefined, {
      skipAuth: true,
      timeout: 5000,
    }),
};

// ─── Metrics API ───────────────────────────────────────────

export const metrics = {
  snapshot: () => request<MetricsSnapshot>("GET", "/metrics/snapshot"),
  evaluation: (queryId: string) =>
    request<EvaluationResult>("GET", `/query/${queryId}/eval`),
};

// ─── Experiments API (AES) ─────────────────────────────────

export interface ExperimentTrial {
  trial_id: string;
  trial_number?: number;
  campaign_id?: string;
  strategy?: string;
  status?: string;
  hypothesis?: string;
  parameters: Record<string, any>;
  objective_score?: number;
  mean_quality?: number;
  p95_latency_ms?: number;
  mean_healing_count?: number;
  metrics?: {
    grounding_score: number;
    faithfulness: number;
    answer_relevance: number;
    p95_latency_ms: number;
    cost_usd: number;
    composite_score: number;
    confidence_interval_95?: [number, number];
    p_value_vs_baseline?: number;
    statistically_significant?: boolean;
  };
  statistical_summary?: {
    is_statistically_significant: boolean;
    wilcoxon_p_value?: number;
    ci_lower_95: number;
    ci_upper_95: number;
  };
  created_at?: string;
}

export interface ExperimentCampaign {
  campaign_id: string;
  name?: string;
  objective?: string;
  status?: string;
  baseline_strategy: string;
  dataset_version?: string;
  best_trial_id?: string;
  best_score?: number;
  total_trials?: number;
  trials?: ExperimentTrial[];
  created_at: string;
}

export const experiments = {
  list: () => request<ExperimentCampaign[]>("GET", "/experiments/campaigns"),
  get: (id: string) => request<ExperimentCampaign>("GET", `/experiments/campaigns/${id}`),
  report: (id: string) => request<string>("GET", `/experiments/campaigns/${id}/report`),
  start: (req?: { name?: string; strategy?: string; max_trials?: number; p95_sla?: number; dataset_version?: string }) =>
    request<{ status: string; campaign_id?: string }>("POST", "/experiments/campaigns", req || {}),
};
