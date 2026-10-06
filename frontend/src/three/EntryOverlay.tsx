import { useEffect, useState, type FormEvent } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Loader2, Lock, Terminal, User } from "lucide-react";
import { authApi } from "../lib/api";
import type { AuthPublicConfig } from "../types";
import { useScene, useSceneState } from "./sceneStore";

const BOOT_LINES = ["INITIALIZING…", "ESTABLISHING CONNECTION…", "SYSTEM READY"];

function BootStatus() {
  const [line, setLine] = useState(0);
  useEffect(() => {
    if (line >= BOOT_LINES.length - 1) return;
    const t = window.setTimeout(() => setLine((l) => l + 1), 480);
    return () => window.clearTimeout(t);
  }, [line]);
  return (
    <motion.p
      key={line}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="num text-[10px] uppercase tracking-[0.3em] text-slate-500"
      aria-live="polite"
    >
      {BOOT_LINES[line]}
    </motion.p>
  );
}

function LoginPanel({ onSuccess }: { onSuccess: () => void }) {
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
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
      setBusy(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 24, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -14, scale: 0.98 }}
      transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
      className="w-full max-w-sm rounded-2xl border border-slate-400/10 bg-ink-900/55 p-7 shadow-[0_24px_70px_-20px_rgba(0,0,0,0.7)] backdrop-blur-md"
      role="dialog"
      aria-label="Sign in"
    >
      <div className="mb-6 text-center">
        <p className="num text-sm font-semibold tracking-[0.35em] text-slate-100">AGENTOPS</p>
        <p className="mt-1 text-[10px] uppercase tracking-[0.22em] text-slate-500">
          Autonomous Fleet Intelligence
        </p>
      </div>
      <form onSubmit={submit} className="space-y-3.5">
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
        <button
          type="submit"
          disabled={busy}
          className="btn btn-primary w-full justify-center py-2.5 text-sm tracking-wide"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
          {busy ? "Authenticating…" : "SIGN IN"}
        </button>
      </form>
      {config?.show_demo_creds && (
        <p className="num mt-4 text-center text-[10px] text-slate-600">
          demo — {config.demo_username} / {config.demo_password}
        </p>
      )}
    </motion.div>
  );
}

/** HTML overlay for the pre-auth scene states: boot status, brand, the
 * ENTER SYSTEM trigger, and the floating login panel. */
export function EntryOverlay({ onAuthenticated }: { onAuthenticated: () => void }) {
  const scene = useScene();
  const state = useSceneState();
  const [autoOpened, setAutoOpened] = useState(false);

  // Optional: auto-open login after a while (supports both trigger styles)
  useEffect(() => {
    if (state !== "GLOBE_ACTIVE" || autoOpened) return;
    const t = window.setTimeout(() => {
      setAutoOpened(true);
      beginLogin();
    }, 30000);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, autoOpened]);

  const beginLogin = () => {
    scene.transitionTo("LOGIN_TRANSITION");
    window.setTimeout(() => scene.transitionTo("LOGIN"), 1200);
  };

  const handleSuccess = () => {
    scene.transitionTo("AUTHENTICATED");
    window.setTimeout(() => scene.transitionTo("SPACE_BACKGROUND"), 900);
    onAuthenticated();
  };

  return (
    <div className="pointer-events-none fixed inset-0 z-10 flex flex-col">
      {/* Brand mark */}
      <div className="flex items-center gap-2.5 p-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-sky-500/30 bg-sky-500/10">
          <Terminal className="h-4 w-4 text-sky-400" />
        </div>
        <span className="num text-xs font-semibold tracking-[0.3em] text-slate-200">AGENTOPS</span>
      </div>

      {/* Center content per state */}
      <div className="flex flex-1 items-end justify-center pb-14 lg:items-center lg:pb-0">
        <AnimatePresence mode="wait">
          {state === "BOOT" && (
            <motion.div key="boot" exit={{ opacity: 0 }} className="pb-4">
              <BootStatus />
            </motion.div>
          )}

          {state === "GLOBE_ACTIVE" && (
            <motion.div
              key="enter"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.5 }}
              className="pointer-events-auto flex flex-col items-center gap-4"
            >
              <button
                onClick={beginLogin}
                className="group num flex items-center gap-3 rounded-full border border-sky-400/25 bg-sky-500/10 px-7 py-3 text-xs font-semibold tracking-[0.28em] text-sky-200 backdrop-blur-sm transition-all hover:border-sky-300/50 hover:bg-sky-500/20 hover:text-sky-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
              >
                ENTER SYSTEM
                <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
              </button>
              <p className="text-[10px] uppercase tracking-[0.24em] text-slate-600">
                drag the earth · it is alive
              </p>
            </motion.div>
          )}

          {(state === "LOGIN" || state === "LOGIN_TRANSITION" || state === "AUTHENTICATED") && (
            <motion.div key="login" className="pointer-events-auto lg:ml-auto lg:pr-[10vw]">
              {state === "LOGIN" || state === "AUTHENTICATED" ? (
                <LoginPanel onSuccess={handleSuccess} />
              ) : (
                <div className="h-64 w-full max-w-sm" />
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
