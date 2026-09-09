"use client";

import { useEffect, useState } from "react";
import { useTheme } from "@/lib/theme";
import { Sun, Moon } from "lucide-react";

export default function ThemeToggle() {
  const { resolved, toggle } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <button
        type="button"
        aria-label="Toggle theme"
        className="w-8 h-8 rounded-lg flex items-center justify-center border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-400"
      >
        <Moon size={14} />
      </button>
    );
  }

  const isDark = resolved === "dark";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={`Switch to ${isDark ? "light" : "dark"} theme`}
      title={`Switch to ${isDark ? "light" : "dark"} theme`}
      className="w-8 h-8 rounded-lg flex items-center justify-center border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-all duration-200 cursor-pointer shadow-2xs group"
    >
      {isDark ? (
        <Sun
          size={14}
          className="text-amber-400 group-hover:rotate-45 transition-transform duration-300"
        />
      ) : (
        <Moon
          size={14}
          className="text-slate-600 dark:text-slate-400 group-hover:-rotate-12 transition-transform duration-300"
        />
      )}
    </button>
  );
}
