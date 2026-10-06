import { Link } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Cog,
  FlaskConical,
  SearchCheck,
  Siren,
} from "lucide-react";
import { timeOfDay } from "../lib/format";
import type { FeedItem } from "../types";
import { EmptyState, Panel } from "./primitives";
import { useApp } from "../hooks/store";

const KIND_ICON: Record<string, JSX.Element> = {
  critical: <AlertTriangle className="h-3 w-3 text-red-400" />,
  warning: <AlertTriangle className="h-3 w-3 text-amber-400" />,
  incident: <Siren className="h-3 w-3 text-orange-400" />,
  agent: <Bot className="h-3 w-3 text-sky-400" />,
  decision: <Bot className="h-3 w-3 text-violet-400" />,
  remediation: <Cog className="h-3 w-3 text-amber-300" />,
  recovery: <SearchCheck className="h-3 w-3 text-emerald-300" />,
  resolved: <CheckCircle2 className="h-3 w-3 text-emerald-400" />,
  inject: <FlaskConical className="h-3 w-3 text-fuchsia-400" />,
};

function FeedRow({ item }: { item: FeedItem }) {
  const inner = (
    <div className="flex items-start gap-2.5 px-3 py-2">
      <span className="num mt-0.5 shrink-0 text-[10px] text-slate-600">{timeOfDay(item.ts)}</span>
      <span className="mt-0.5 shrink-0">{KIND_ICON[item.kind] ?? KIND_ICON.agent}</span>
      <div className="min-w-0">
        <p className="truncate text-[11px] text-slate-300">{item.title}</p>
        {item.detail && <p className="truncate text-[10px] text-slate-500">{item.detail}</p>}
      </div>
    </div>
  );
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -8, backgroundColor: "rgba(56,189,248,0.08)" }}
      animate={{ opacity: 1, y: 0, backgroundColor: "rgba(56,189,248,0)" }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.35 }}
      className="border-b border-line/50 last:border-0 hover:bg-ink-800/40"
    >
      {item.incident_id ? <Link to={`/incidents/${item.incident_id}`}>{inner}</Link> : inner}
    </motion.div>
  );
}

export function ActivityFeed() {
  const { feed } = useApp();
  return (
    <Panel title="Live Agent Activity" className="flex h-full min-h-0 flex-col" pad={false}>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {feed.length === 0 ? (
          <EmptyState
            title="Waiting for activity"
            hint="Agent actions, anomalies and incidents will stream here in real time."
          />
        ) : (
          <ul>
            <AnimatePresence initial={false}>
              {feed.map((item) => (
                <FeedRow key={item.id} item={item} />
              ))}
            </AnimatePresence>
          </ul>
        )}
      </div>
    </Panel>
  );
}
