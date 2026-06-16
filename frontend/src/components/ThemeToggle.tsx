/**
 * ThemeToggle — Sun/Moon icon button with glassmorphism
 *
 * Sits in the navbar. Cycles light ↔ dark (system read on first visit).
 */
"use client";

import { useTheme } from "@/lib/theme";
import { Sun, Moon } from "lucide-react";

export default function ThemeToggle() {
  const { resolved, toggle } = useTheme();

  return (
    <button
      onClick={toggle}
      aria-label="Toggle theme"
      className="theme-toggle"
    >
      <span className="theme-toggle-icon">
        <Sun size={14} className="theme-sun" />
        <Moon size={14} className="theme-moon" />
      </span>
    </button>
  );
}
