/**
 * Theme Provider — Light / Dark / System
 *
 * Persists to localStorage, respects OS prefers-color-scheme,
 * sets data-theme on <html>, exposes useTheme() hook.
 */
"use client";

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";

type Theme = "light" | "dark" | "system";
type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "nexus-theme";

interface ThemeCtx {
  /** User-selected preference (may be "system") */
  theme: Theme;
  /** Resolved — always "light" or "dark" */
  resolved: ResolvedTheme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeCtx | null>(null);

/** Read stored preference, or "light" if absent */
function getStored(): Theme {
  if (typeof window === "undefined") return "light";
  const v = localStorage.getItem(STORAGE_KEY);
  if (v === "light" || v === "dark" || v === "system") return v;
  return "light";
}

/** Resolve user + OS to a concrete theme, defaulting to light */
function resolve(t: Theme): ResolvedTheme {
  if (t === "light") return "light";
  if (t === "dark") return "dark";
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Apply data-theme to <html>, called during render to avoid flash */
export function applyTheme(t: Theme): void {
  const r = resolve(t);
  document.documentElement.setAttribute("data-theme", r);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(getStored);
  const [resolved, setResolved] = useState<ResolvedTheme>(resolve(theme));
  const [mounted, setMounted] = useState(false);

  // Apply on mount (catches SSR → client transition)
  useEffect(() => {
    applyTheme(theme);
    setResolved(resolve(theme));
    setMounted(true);
  }, [theme]);

  // Listen for OS preference changes
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const handler = () => {
      if (getStored() === "system" || !localStorage.getItem(STORAGE_KEY)) {
        const r = resolve("system");
        setResolved(r);
        document.documentElement.setAttribute("data-theme", r);
      }
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const setTheme = useCallback((t: Theme) => {
    localStorage.setItem(STORAGE_KEY, t);
    setThemeState(t);
  }, []);

  const toggle = useCallback(() => {
    const next: Theme = resolved === "dark" ? "light" : "dark";
    localStorage.setItem(STORAGE_KEY, next);
    setThemeState(next);
  }, [resolved]);

  // Avoid hydration mismatch flash
  if (!mounted) {
    return (
      <ThemeContext.Provider value={{ theme, resolved, setTheme, toggle }}>
        <div style={{ opacity: 0 }}>{children}</div>
      </ThemeContext.Provider>
    );
  }

  return (
    <ThemeContext.Provider value={{ theme, resolved, setTheme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
