"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  MessageSquareCode,
  FileText,
  Workflow,
  FlaskConical,
  BarChart2,
  Activity,
  Settings,
  ChevronLeft,
  ChevronRight,
  Brain,
  Sparkles,
} from "lucide-react";

export interface NavItem {
  name: string;
  href: string;
  icon: React.ElementType;
  badge?: string;
  roles?: string[]; // for future RBAC extension
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const NAVIGATION_SECTIONS: NavSection[] = [
  {
    title: "Overview",
    items: [
      { name: "Dashboard", href: "/app/dashboard", icon: LayoutDashboard },
    ],
  },
  {
    title: "Query",
    items: [
      { name: "Live Query", href: "/app/query", icon: MessageSquareCode },
    ],
  },
  {
    title: "Knowledge",
    items: [
      { name: "Documents", href: "/app/documents", icon: FileText },
    ],
  },
  {
    title: "AI Pipeline",
    items: [
      { name: "Pipeline", href: "/app/pipeline", icon: Workflow },
    ],
  },
  {
    title: "Research",
    items: [
      { name: "Scientist Studio", href: "/app/scientist", icon: FlaskConical },
      { name: "Benchmarks", href: "/app/benchmarks", icon: BarChart2 },
    ],
  },
  {
    title: "Operations",
    items: [
      { name: "Observability", href: "/app/observability", icon: Activity },
    ],
  },
  {
    title: "System",
    items: [
      { name: "Settings", href: "/app/settings", icon: Settings },
    ],
  },
];

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen?: boolean;
  onCloseMobile?: () => void;
  userRole?: string;
}

export default function Sidebar({
  collapsed,
  onToggleCollapse,
  mobileOpen = false,
  onCloseMobile,
  userRole,
}: SidebarProps) {
  const pathname = usePathname();

  const isItemActive = (href: string) => {
    if (href === "/app/dashboard") return pathname === "/app/dashboard" || pathname === "/app";
    return pathname.startsWith(href);
  };

  const navContent = (
    <div className="flex flex-col h-full bg-white dark:bg-slate-950 border-r border-slate-200 dark:border-slate-800 transition-all duration-200 select-none">
      {/* Brand Header */}
      <div className="h-14 flex items-center justify-between px-3.5 border-b border-slate-200 dark:border-slate-800">
        <Link
          href="/app/dashboard"
          className="flex items-center gap-2.5 min-w-0 group"
          onClick={onCloseMobile}
        >
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center shrink-0 shadow-xs shadow-blue-500/20 group-hover:scale-105 transition-transform">
            <Brain size={16} className="text-white" />
          </div>
          {!collapsed && (
            <div className="flex flex-col min-w-0">
              <span className="text-xs font-bold tracking-tight text-slate-900 dark:text-slate-100 truncate">
                Nexus Core
              </span>
              <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400 truncate">
                Self-Healing RAG
              </span>
            </div>
          )}
        </Link>

        {/* Desktop Collapse Toggle */}
        <button
          onClick={onToggleCollapse}
          className="hidden md:flex items-center justify-center w-7 h-7 rounded-md text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      {/* Navigation Groups */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden py-3 px-2 space-y-4">
        {NAVIGATION_SECTIONS.map((section) => {
          // Filter items by role if roles are defined on item
          const visibleItems = section.items.filter((item) => {
            if (!item.roles || !userRole) return true;
            return item.roles.includes(userRole);
          });

          if (visibleItems.length === 0) return null;

          return (
            <div key={section.title} className="space-y-0.5">
              {!collapsed && (
                <div className="px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                  {section.title}
                </div>
              )}
              {visibleItems.map((item) => {
                const active = isItemActive(item.href);
                const Icon = item.icon;

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onCloseMobile}
                    title={collapsed ? item.name : undefined}
                    className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs transition-colors group relative ${
                      active
                        ? "bg-blue-50 text-blue-700 font-semibold dark:bg-blue-950/50 dark:text-blue-400"
                        : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-900 hover:text-slate-900 dark:hover:text-slate-200 font-medium"
                    } ${collapsed ? "justify-center px-0" : ""}`}
                  >
                    <Icon
                      size={16}
                      className={`shrink-0 transition-transform group-hover:scale-105 ${
                        active
                          ? "text-blue-600 dark:text-blue-400"
                          : "text-slate-400 dark:text-slate-500 group-hover:text-slate-700 dark:group-hover:text-slate-300"
                      }`}
                    />
                    {!collapsed && (
                      <span className="truncate flex-1">{item.name}</span>
                    )}
                    {!collapsed && item.badge && (
                      <span className="text-[10px] font-mono font-medium px-1.5 py-0.2 rounded bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300">
                        {item.badge}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          );
        })}
      </div>

      {/* Footer / Version */}
      {!collapsed && (
        <div className="p-3 border-t border-slate-200 dark:border-slate-800 text-[11px] text-slate-500 dark:text-slate-400 flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>Multi-Agent v2.4</span>
          </div>
          <span className="font-mono text-[10px] text-slate-400">Prod</span>
        </div>
      )}
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <aside
        className={`hidden md:block shrink-0 transition-all duration-200 ${
          collapsed ? "w-14" : "w-56"
        }`}
      >
        <div className={`fixed top-0 bottom-0 z-30 transition-all duration-200 ${
          collapsed ? "w-14" : "w-56"
        }`}>
          {navContent}
        </div>
      </aside>

      {/* Mobile Drawer Overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-xs md:hidden"
          onClick={onCloseMobile}
        />
      )}

      {/* Mobile Drawer */}
      <div
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 bg-white dark:bg-slate-950 md:hidden transform transition-transform duration-200 ease-in-out ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {navContent}
      </div>
    </>
  );
}
