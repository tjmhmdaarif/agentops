import { useEffect, useState, type FormEvent } from "react";
import { Bot, KeyRound, Lock, SlidersHorizontal } from "lucide-react";
import { EmptyState, Panel } from "../components/primitives";
import { api, authApi } from "../lib/api";
import { useApp } from "../hooks/store";
import type { AppConfig, HealthStatus } from "../types";

function ChangePasswordForm() {
  const { pushToast } = useApp();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (next !== confirm) {
      pushToast("warning", "Passwords do not match");
      return;
    }
    setBusy(true);
    try {
      const r = await authApi.changePassword(current, next);
      pushToast("success", "Password updated", r.message);
      setCurrent(""); setNext(""); setConfirm("");
    } catch (err) {
      pushToast("critical", "Password change failed", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title={<span className="flex items-center gap-1.5"><Lock className="h-3 w-3" /> Change Password</span>}>
      <form onSubmit={submit} className="space-y-3">
        <div>
          <label htmlFor="cp-current" className="label-xs mb-1 block">Current password</label>
          <input id="cp-current" type="password" value={current} onChange={(e) => setCurrent(e.target.value)} className="input" autoComplete="current-password" required />
        </div>
        <div>
          <label htmlFor="cp-new" className="label-xs mb-1 block">New password (min 8 chars)</label>
          <input id="cp-new" type="password" value={next} onChange={(e) => setNext(e.target.value)} className="input" autoComplete="new-password" minLength={8} required />
        </div>
        <div>
          <label htmlFor="cp-confirm" className="label-xs mb-1 block">Confirm new password</label>
          <input id="cp-confirm" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className="input" autoComplete="new-password" minLength={8} required />
        </div>
        <button type="submit" disabled={busy} className="btn btn-primary">
          Update password
        </button>
        <p className="text-[10px] text-slate-600">Changing your password signs out all existing sessions.</p>
      </form>
    </Panel>
  );
}

function Row({ label, value, mono = true }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-line/50 py-2 text-xs last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className={`${mono ? "num" : ""} text-slate-300`}>{value}</span>
    </div>
  );
}

export default function SettingsPage() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);

  useEffect(() => {
    api.config().then(setConfig).catch(() => undefined);
    api.health().then(setHealth).catch(() => undefined);
  }, []);

  if (!config) {
    return <div className="p-4"><EmptyState title="Loading configuration…" /></div>;
  }

  return (
    <div className="space-y-3 p-4">
      <div>
        <h1 className="text-lg font-semibold tracking-tight text-slate-100">Settings</h1>
        <p className="text-xs text-slate-500">Runtime configuration (read-only — set via environment variables)</p>
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <Panel title={<span className="flex items-center gap-1.5"><SlidersHorizontal className="h-3 w-3" /> Detection Thresholds</span>}>
          <Row label="Anomaly threshold (fused score)" value={config.anomaly_threshold.toFixed(2)} />
          <Row label="Persistence (consecutive samples)" value={String(config.anomaly_persistence)} />
          <Row label="Incident cooldown" value={`${config.incident_cooldown_seconds}s`} />
          <Row label="Environment" value={config.app_env} />
        </Panel>

        <Panel title={<span className="flex items-center gap-1.5"><Bot className="h-3 w-3" /> Agent</span>}>
          <Row label="LLM mode" value={config.llm_enabled ? "enabled" : "disabled"} />
          <Row label="Provider" value={config.llm_provider} />
          <Row label="Model" value={config.llm_model} />
          <Row label="Active planner" value={health?.agent === "llm" ? "LLM (validated)" : "deterministic rule engine"} />
        </Panel>

        <ChangePasswordForm />

        <Panel title={<span className="flex items-center gap-1.5"><SlidersHorizontal className="h-3 w-3" /> Feature Flags</span>}>
          {Object.keys(config.feature_flags ?? {}).length === 0 ? (
            <p className="text-xs text-slate-500">No flags configured.</p>
          ) : (
            Object.entries(config.feature_flags).map(([name, on]) => (
              <Row key={name} label={name.replace(/_/g, " ")} value={on ? "ON" : "off"} />
            ))
          )}
          <p className="mt-2 text-[10px] leading-relaxed text-slate-600">
            Flags are set via the FEATURE_FLAGS environment variable (e.g.
            FEATURE_FLAGS="predictive_health=true") and gate experimental features
            so main stays shippable. See docs/RELEASE_PROCESS.md.
          </p>
        </Panel>
      </div>

      <Panel title={<span className="flex items-center gap-1.5"><KeyRound className="h-3 w-3" /> Enabling LLM Mode</span>}>
        <div className="space-y-2 text-xs leading-relaxed text-slate-400">
          <p>
            AgentOps works fully without any API key — the deterministic rule engine investigates,
            decides and remediates on its own. To let an LLM choose actions from the same strict
            tool registry instead:
          </p>
          <pre className="num overflow-x-auto rounded-lg border border-line bg-ink-950/80 p-3 text-[11px] text-slate-300">
{`LLM_ENABLED=true
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5
ANTHROPIC_API_KEY=sk-ant-...`}
          </pre>
          <p>
            The LLM response is validated with Pydantic. On any failure — timeout, invalid JSON,
            unknown tool, network error — the system falls back to deterministic rules automatically.
          </p>
        </div>
      </Panel>
    </div>
  );
}
