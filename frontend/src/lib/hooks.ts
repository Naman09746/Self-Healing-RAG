/**
 * React Hooks — Self-Healing RAG
 *
 * Custom hooks for real-time data fetching, SSE streaming,
 * auth state, and metrics polling.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import {
  health,
  query as queryApi,
  documents as docsApi,
  metrics as metricsApi,
  experiments as experimentsApi,
  auth as authApi,
  isAuthenticated,
  getAccessToken,
  setTokens,
  clearTokens,
  type QueryResponse,
  type DocumentInfo,
  type HealthStatus,
  type MetricsSnapshot,
  type UserProfile,
  type ExperimentCampaign,
  type ExperimentTrial,
} from "./api";

// ─── Health Check ─────────────────────────────────────────

export function useHealth(pollInterval = 30000) {
  const [status, setStatus] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const check = useCallback(async () => {
    try {
      const result = await health.check();
      setStatus(result);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    check();
    const interval = setInterval(check, pollInterval);
    return () => clearInterval(interval);
  }, [check, pollInterval]);

  return { status, loading, error, refresh: check };
}

// ─── Documents ────────────────────────────────────────────

export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const fetch = useCallback(async () => {
    try {
      const result = await docsApi.list();
      setDocuments(result);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  const upload = useCallback(async (file: File) => {
    setUploading(true);
    try {
      const result = await docsApi.upload(file);
      await fetch(); // Refresh list
      return result;
    } catch (err) {
      setError((err as Error).message);
      throw err;
    } finally {
      setUploading(false);
    }
  }, [fetch]);

  const remove = useCallback(async (id: string) => {
    try {
      await docsApi.delete(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  return { documents, loading, error, uploading, upload, remove, refresh: fetch };
}

// ─── Query / Chat ─────────────────────────────────────────

export function useQuery() {
  const [processing, setProcessing] = useState(false);
  const [lastResponse, setLastResponse] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [streaming, setStreaming] = useState(false);

  const ask = useCallback(async (question: string, sessionId?: string) => {
    setProcessing(true);
    setError(null);
    try {
      const response = await queryApi.ask({
        query: question,
        session_id: sessionId || undefined,
      });
      setLastResponse(response);
      return response;
    } catch (err) {
      setError((err as Error).message);
      return null;
    } finally {
      setProcessing(false);
    }
  }, []);

  const askStream = useCallback((
    question: string,
    callbacks: {
      onToken?: (token: string) => void;
      onPhase?: (phase: string) => void;
      onComplete?: (result: QueryResponse) => void;
      onError?: (err: Error) => void;
    },
    sessionId?: string,
  ) => {
    setStreaming(true);
    setError(null);

    const controller = queryApi.askStream(
      { query: question, session_id: sessionId || undefined, stream: true },
      {
        onToken: callbacks.onToken,
        onPhase: callbacks.onPhase,
        onComplete: (result) => {
          setLastResponse(result);
          setStreaming(false);
          callbacks.onComplete?.(result);
        },
        onError: (err) => {
          setError(err.message);
          setStreaming(false);
          callbacks.onError?.(err);
        },
      },
    );

    abortRef.current = controller;
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setProcessing(false);
    setStreaming(false);
  }, []);

  return { ask, askStream, cancel, processing, streaming, lastResponse, error };
}

// ─── Metrics Polling ──────────────────────────────────────

export function useMetrics(pollInterval = 15000) {
  const [metrics, setMetrics] = useState<MetricsSnapshot | null>(null);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    try {
      const result = await metricsApi.snapshot();
      setMetrics(result);
    } catch {
      // Silently handle — metrics endpoint may not be available
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
    const interval = setInterval(fetch, pollInterval);
    return () => clearInterval(interval);
  }, [fetch, pollInterval]);

  return { metrics, loading, refresh: fetch };
}

// ─── Experiments (AES) ────────────────────────────────────

export function useExperiments(pollInterval = 30000) {
  const [campaigns, setCampaigns] = useState<ExperimentCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCampaigns = useCallback(async () => {
    try {
      const data = await experimentsApi.list();
      setCampaigns(data || []);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCampaigns();
    const interval = setInterval(fetchCampaigns, pollInterval);
    return () => clearInterval(interval);
  }, [fetchCampaigns, pollInterval]);

  const startCampaign = useCallback(
    async (params?: { name?: string; strategy?: string; max_trials?: number; p95_sla?: number }) => {
      try {
        const res = await experimentsApi.start(params);
        await fetchCampaigns();
        return res;
      } catch (err) {
        setError((err as Error).message);
        throw err;
      }
    },
    [fetchCampaigns]
  );

  return { campaigns, loading, error, refresh: fetchCampaigns, startCampaign };
}

// ─── Auth ─────────────────────────────────────────────────

export function useAuth() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    const check = async () => {
      const authed = isAuthenticated();
      setAuthenticated(authed);
      if (authed) {
        try {
          const profile = await authApi.profile();
          setUser(profile);
        } catch {
          clearTokens();
          setAuthenticated(false);
        }
      }
      setLoading(false);
    };
    check();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const result = await authApi.login(email, password);
    setTokens(result.access_token, result.refresh_token);
    setAuthenticated(true);
    const profile = await authApi.profile();
    setUser(profile);
    return profile;
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    setAuthenticated(false);
  }, []);

  return { user, loading, authenticated, login, logout };
}

// ─── Debounce ─────────────────────────────────────────────

export function useDebounce<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timeout = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timeout);
  }, [value, delayMs]);

  return debounced;
}

// ─── Local Storage State ──────────────────────────────────

export function useLocalStorage<T>(key: string, initial: T): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    if (typeof window === "undefined") return initial;
    try {
      const stored = localStorage.getItem(key);
      return stored ? (JSON.parse(stored) as T) : initial;
    } catch {
      return initial;
    }
  });

  const set = useCallback((v: T) => {
    setValue(v);
    try {
      localStorage.setItem(key, JSON.stringify(v));
    } catch {
      // Storage full or unavailable
    }
  }, [key]);

  return [value, set];
}
