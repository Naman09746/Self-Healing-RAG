"use client";

import { useState, useRef, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Menu,
  Search,
  HelpCircle,
  LogOut,
  User,
  Shield,
  CheckCircle2,
  AlertTriangle,
  Building,
  ChevronDown,
} from "lucide-react";
import ThemeToggle from "@/components/ThemeToggle";
import { useAuth, useHealth } from "@/lib/hooks";

interface TopbarProps {
  onOpenMobileMenu: () => void;
}

const PAGE_TITLES: Record<string, { title: string; category: string }> = {
  "/app": { title: "Dashboard", category: "Overview" },
  "/app/dashboard": { title: "Dashboard", category: "Overview" },
  "/app/query": { title: "Live Query", category: "Query" },
  "/app/documents": { title: "Documents & Knowledge Base", category: "Knowledge" },
  "/app/pipeline": { title: "AI Pipeline Visualizer", category: "AI Pipeline" },
  "/app/scientist": { title: "Scientist Studio (AES)", category: "Research" },
  "/app/benchmarks": { title: "Evaluation & Benchmarks", category: "Research" },
  "/app/observability": { title: "Observability & Telemetry", category: "Operations" },
  "/app/settings": { title: "Settings & Configuration", category: "System" },
};

export default function Topbar({ onOpenMobileMenu }: TopbarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const { status: healthStatus } = useHealth(30000);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentRouteInfo = PAGE_TITLES[pathname] || {
    title: pathname.replace("/app/", "").replace("-", " ").toUpperCase(),
    category: "Nexus Core",
  };

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setUserDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSignOut = () => {
    logout();
    router.push("/login");
  };

  const isHealthy = healthStatus?.status === "healthy";

  return (
    <header className="h-14 bg-white/90 dark:bg-slate-950/90 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 px-4 flex items-center justify-between sticky top-0 z-20">
      {/* Left: Mobile Toggle & Breadcrumb */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onOpenMobileMenu}
          className="md:hidden flex items-center justify-center w-8 h-8 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          aria-label="Open navigation menu"
        >
          <Menu size={18} />
        </button>

        <div className="flex items-center gap-2 text-xs truncate">
          <span className="text-slate-400 dark:text-slate-500 font-medium hidden sm:inline">
            {currentRouteInfo.category}
          </span>
          <span className="text-slate-300 dark:text-slate-600 hidden sm:inline">/</span>
          <h1 className="text-slate-900 dark:text-slate-100 font-bold truncate">
            {currentRouteInfo.title}
          </h1>
        </div>
      </div>

      {/* Right: Tenant, System Health, Search, Help, Theme, User Profile */}
      <div className="flex items-center gap-2.5 sm:gap-3">
        {/* Tenant Indicator */}
        <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-600 dark:text-slate-400">
          <Building size={12} className="text-slate-400" />
          <span>Tenant:</span>
          <span className="font-semibold text-slate-800 dark:text-slate-200">
            {user?.tenant_id || "default"}
          </span>
        </div>

        {/* Backend Health Status Badge */}
        <Link
          href="/app/observability"
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium transition-colors border ${
            isHealthy
              ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800"
              : "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800"
          }`}
          title="View System Health & Observability"
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              isHealthy ? "bg-emerald-500" : "bg-amber-500 animate-pulse"
            }`}
          />
          <span className="hidden sm:inline">
            {isHealthy ? "Healthy" : "Degraded"}
          </span>
        </Link>

        {/* Documentation / Help Link */}
        <Link
          href="/docs"
          className="hidden sm:flex items-center justify-center w-8 h-8 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          title="Documentation"
        >
          <HelpCircle size={16} />
        </Link>

        {/* Theme Toggle */}
        <ThemeToggle />

        {/* User Menu Dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setUserDropdownOpen(!userDropdownOpen)}
            className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors text-left"
            aria-expanded={userDropdownOpen}
            aria-label="User profile menu"
          >
            <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white text-xs font-bold shadow-2xs">
              {user?.email ? user.email.charAt(0).toUpperCase() : "U"}
            </div>
            <div className="hidden xl:flex flex-col min-w-0 text-xs">
              <span className="font-semibold text-slate-800 dark:text-slate-200 truncate max-w-[120px]">
                {user?.email?.split("@")[0] || "Operator"}
              </span>
              <span className="text-[10px] text-slate-400 font-mono capitalize">
                {user?.role || "Admin"}
              </span>
            </div>
            <ChevronDown size={12} className="text-slate-400 hidden sm:inline" />
          </button>

          {userDropdownOpen && (
            <div className="absolute right-0 mt-1.5 w-56 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-lg py-1.5 text-xs z-50 animate-in fade-in zoom-in-95 duration-100">
              <div className="px-3 py-2 border-b border-slate-100 dark:border-slate-800">
                <p className="font-semibold text-slate-900 dark:text-slate-100 truncate">
                  {user?.email || "admin@self-healing-rag.local"}
                </p>
                <p className="text-[11px] text-slate-500 font-mono capitalize">
                  Role: {user?.role || "admin"}
                </p>
              </div>

              <Link
                href="/app/settings"
                onClick={() => setUserDropdownOpen(false)}
                className="flex items-center gap-2 px-3 py-2 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors"
              >
                <User size={14} />
                <span>Account Settings</span>
              </Link>

              <Link
                href="/docs"
                onClick={() => setUserDropdownOpen(false)}
                className="flex items-center gap-2 px-3 py-2 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors"
              >
                <HelpCircle size={14} />
                <span>API & Documentation</span>
              </Link>

              <div className="my-1 border-t border-slate-100 dark:border-slate-800" />

              <button
                onClick={handleSignOut}
                className="w-full flex items-center gap-2 px-3 py-2 text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition-colors text-left"
              >
                <LogOut size={14} />
                <span>Sign Out</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
