import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Activity,
  BarChart3,
  Cpu,
  LayoutDashboard,
  Radio,
  Settings as SettingsIcon,
  Siren,
  Terminal,
} from "lucide-react";
import { LogOut } from "lucide-react";
import { useApp } from "../hooks/store";
import { useAuth } from "../hooks/auth";
import { api } from "../lib/api";
import type { HealthStatus } from "../types";
import { Toasts } from "./Toasts";

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/fleet", label: "Fleet", icon: Cpu },
  { to: "/incidents", label: "Incidents", icon: Siren },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/simulation", label: "Simulation", icon: Radio },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

function SystemFooter() {
  const { sim, connection } = useApp();
  const { username, logout } = useAuth();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  useEffect(() => {
    const load = () => api.health().then(setHealth).catch(() => setHealth(null));
    load();
    const t = window.setInterval(load, 15000);
    return () => window.clearInterval(t);
  }, []);
  const rows = [
    { label: "Backend", ok: !!health, value: health ? health.status : "offline" },
    { label: "Simulation", ok: sim?.status === "RUNNING", value: (sim?.status ?? "…").toLowerCase() },
    { label: "Agent", ok: true, value: health?.agent === "llm" ? "LLM planner" : "rule engine" },
    { label: "LLM", ok: health?.llm === "enabled", value: health?.llm ?? "disabled" },
    { label: "Stream", ok: connection === "live", value: connection },
  ];
  return (
    <div className="border-t border-line px-4 py-3">
      <p className="label-xs mb-2">System</p>
      <ul className="space-y-1.5">
        {rows.map((r) => (
          <li key={r.label} className="flex items-center justify-between text-[11px]">
            <span className="text-slate-500">{r.label}</span>
            <span className="flex items-center gap-1.5 text-slate-400">
              <span className={`h-1.5 w-1.5 rounded-full ${r.ok ? "bg-emerald-400" : "bg-slate-600"}`} />
              {r.value}
            </span>
          </li>
        ))}
      </ul>
      <button
        onClick={logout}
        className="mt-3 flex w-full items-center justify-between rounded-lg border border-line px-2.5 py-1.5 text-[11px] text-slate-400 transition-colors hover:border-slate-500/40 hover:text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/60"
        aria-label="Sign out"
      >
        <span className="num">{username}</span>
        <span className="flex items-center gap-1"><LogOut className="h-3 w-3" /> Sign out</span>
      </button>
    </div>
  );
}

export default function Layout() {
  const { connection } = useApp();
  const location = useLocation();
  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="flex w-52 shrink-0 flex-col border-r border-line bg-ink-900/60">
        <div className="flex items-center gap-2.5 px-4 py-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-sky-500/30 bg-sky-500/10">
            <Terminal className="h-4 w-4 text-sky-400" />
          </div>
          <div>
            <p className="text-sm font-semibold tracking-tight text-slate-100">AgentOps</p>
            <p className="text-[10px] text-slate-500">Fleet Intelligence</p>
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 px-2 py-2" aria-label="Main navigation">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `group flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/60 ${
                  isActive
                    ? "bg-ink-800 text-slate-100 shadow-panel"
                    : "text-slate-400 hover:bg-ink-800/50 hover:text-slate-200"
                }`
              }
            >
              <item.icon className="h-3.5 w-3.5" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <SystemFooter />
      </aside>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {connection !== "live" && (
          <div className="flex items-center gap-2 border-b border-amber-500/30 bg-amber-500/10 px-4 py-1.5 text-[11px] text-amber-300" role="alert">
            <Activity className="h-3 w-3" />
            Live connection interrupted — reconnecting automatically…
          </div>
        )}
        <main className="min-h-0 flex-1 overflow-y-auto">
          {/* Keyed remount animates page entry; no AnimatePresence exit phase —
              mode="wait" can strand children at opacity 0 under StrictMode. */}
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="h-full"
          >
            <Outlet />
          </motion.div>
        </main>
      </div>
      <Toasts />
    </div>
  );
}
