import { AnimatePresence, motion } from "framer-motion";
import { AlertOctagon, AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { useApp } from "../hooks/store";

const ICONS = {
  info: <Info className="h-4 w-4 text-sky-400" />,
  success: <CheckCircle2 className="h-4 w-4 text-emerald-400" />,
  warning: <AlertTriangle className="h-4 w-4 text-amber-400" />,
  critical: <AlertOctagon className="h-4 w-4 text-red-400" />,
};

const BORDER = {
  info: "border-sky-500/30",
  success: "border-emerald-500/30",
  warning: "border-amber-500/30",
  critical: "border-red-500/40",
};

export function Toasts() {
  const { toasts, dismissToast } = useApp();
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2" role="status" aria-live="polite">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            layout
            initial={{ opacity: 0, x: 40, scale: 0.96 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 24, scale: 0.96 }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
            className={`pointer-events-auto flex items-start gap-2.5 rounded-xl border ${BORDER[t.kind]} bg-ink-850/95 p-3 shadow-panel backdrop-blur`}
          >
            <div className="mt-0.5 shrink-0">{ICONS[t.kind]}</div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-slate-200">{t.title}</p>
              {t.detail && <p className="mt-0.5 truncate text-[11px] text-slate-400">{t.detail}</p>}
            </div>
            <button
              onClick={() => dismissToast(t.id)}
              className="rounded p-0.5 text-slate-500 transition-colors hover:text-slate-300 focus:outline-none focus-visible:ring-1 focus-visible:ring-sky-500"
              aria-label="Dismiss notification"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
