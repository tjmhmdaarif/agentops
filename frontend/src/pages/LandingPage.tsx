import { useEffect, useState, type FormEvent } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowRight,
  Bot,
  Loader2,
  Lock,
  Radar,
  SearchCheck,
  ShieldCheck,
  Terminal,
  User,
  Wrench,
} from "lucide-react";
import { authApi } from "../lib/api";
import type { AuthPublicConfig } from "../types";

const FEATURES = [
  {
    icon: <Radar className="h-4 w-4 text-sky-400" />,
    title: "Hybrid anomaly detection",
    body: "Robust z-score, EWMA divergence, rate-of-change and Isolation Forests fused into one explainable score.",
  },
  {
    icon: <Bot className="h-4 w-4 text-violet-400" />,
    title: "Autonomous incident agent",
    body: "Investigates with registered tools, explains every decision, remediates within a strict safety model.",
  },
  {
    icon: <SearchCheck className="h-4 w-4 text-emerald-400" />,
    title: "Verified recovery",
    body: "Incidents close only after telemetry proves the device returned to its learned baseline.",
  },
  {
    icon: <Wrench className="h-4 w-4 text-amber-400" />,
    title: "Failure injection",
    body: "Twelve realistic fault scenarios on a living simulated fleet — no hardware required.",
  },
];

function LoginCard({ onLogin }: { onLogin: () => void }) {
  const [config, setConfig] = useState<AuthPublicConfig | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    authApi.publicConfig().then((c) => {
      setConfig(c);
      if (c.show_demo_creds) {
        setUsername(c.demo_username);
        setPassword(c.demo_password);
      }
    }).catch(() => undefined);
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await authApi.login(username, password);
      onLogin();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
      setBusy(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15, duration: 0.4 }}
      className="panel w-full max-w-sm p-6"
    >
      <div className="mb-5 flex items-center gap-2">
        <Lock className="h-4 w-4 text-slate-500" />
        <h2 className="text-sm font-semibold text-slate-200">Operator sign-in</h2>
      </div>
      <form onSubmit={submit} className="space-y-3">
        <div>
          <label htmlFor="login-username" className="label-xs mb-1 block">Username</label>
          <div className="relative">
            <User className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-600" />
            <input
              id="login-username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="input pl-8"
              autoComplete="username"
              required
            />
          </div>
        </div>
        <div>
          <label htmlFor="login-password" className="label-xs mb-1 block">Password</label>
          <div className="relative">
            <Lock className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-600" />
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input pl-8"
              autoComplete="current-password"
              required
            />
          </div>
        </div>
        {error && (
          <motion.p
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300"
            role="alert"
          >
            {error}
          </motion.p>
        )}
        <button type="submit" disabled={busy} className="btn btn-primary w-full justify-center py-2 text-sm">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
          {busy ? "Signing in…" : "Enter the fleet"}
        </button>
      </form>
      {config?.show_demo_creds && (
        <p className="num mt-4 rounded-lg border border-line bg-ink-950/60 px-3 py-2 text-center text-[10px] text-slate-500">
          demo credentials — {config.demo_username} / {config.demo_password}
        </p>
      )}
    </motion.div>
  );
}

export default function LandingPage({ onLogin }: { onLogin: () => void }) {
  return (
    <div className="relative flex min-h-full flex-col overflow-y-auto">
      {/* Ambient background */}
      <div className="pointer-events-none absolute inset-0" aria-hidden>
        <div className="absolute left-1/2 top-0 h-[420px] w-[820px] -translate-x-1/2 rounded-full bg-sky-500/[0.07] blur-3xl" />
        <div
          className="absolute inset-0 opacity-[0.13]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(148,163,184,0.09) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.09) 1px, transparent 1px)",
            backgroundSize: "44px 44px",
            maskImage: "radial-gradient(ellipse 80% 60% at 50% 0%, black, transparent)",
          }}
        />
      </div>

      <header className="relative z-10 flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-sky-500/30 bg-sky-500/10">
            <Terminal className="h-4 w-4 text-sky-400" />
          </div>
          <span className="text-sm font-semibold tracking-tight text-slate-100">AgentOps</span>
          <span className="rounded-md border border-line px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-widest text-slate-500">
            v2.0
          </span>
        </div>
        <span className="flex items-center gap-1.5 text-[11px] text-slate-500">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
          No LLM key required
        </span>
      </header>

      <main className="relative z-10 mx-auto flex w-full max-w-6xl flex-1 flex-col items-center gap-10 px-6 pb-16 pt-10 lg:flex-row lg:items-start lg:gap-16 lg:pt-16">
        <div className="max-w-xl flex-1 text-center lg:text-left">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            <p className="mb-3 inline-flex items-center gap-2 rounded-full border border-sky-500/25 bg-sky-500/10 px-3 py-1 text-[11px] font-medium text-sky-300">
              <Activity className="h-3 w-3" /> Autonomous IoT Fleet Intelligence
            </p>
            <h1 className="text-4xl font-bold leading-[1.05] tracking-tight text-slate-50 lg:text-5xl">
              Detect. Investigate.
              <span className="bg-gradient-to-r from-sky-400 to-emerald-400 bg-clip-text text-transparent"> Remediate.</span>
            </h1>
            <p className="mt-4 text-sm leading-relaxed text-slate-400 lg:text-base">
              A living fleet of edge devices streams telemetry. An anomaly engine finds the faults.
              An autonomous agent investigates, explains, fixes — and proves recovery before closing
              the incident. Watch the whole loop happen, live.
            </p>
          </motion.div>

          <div className="mt-8 grid gap-3 sm:grid-cols-2">
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + i * 0.07, duration: 0.35 }}
                className="panel-inset p-3.5 text-left"
              >
                <div className="flex items-center gap-2">
                  {f.icon}
                  <h3 className="text-xs font-semibold text-slate-200">{f.title}</h3>
                </div>
                <p className="mt-1.5 text-[11px] leading-relaxed text-slate-500">{f.body}</p>
              </motion.div>
            ))}
          </div>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="num mt-8 text-[10px] uppercase tracking-[0.2em] text-slate-600"
          >
            FastAPI · scikit-learn · SQLite · SSE · React · TypeScript
          </motion.p>
        </div>

        <div className="flex w-full max-w-sm justify-center lg:pt-10">
          <LoginCard onLogin={onLogin} />
        </div>
      </main>
    </div>
  );
}
