import { useState } from "react";
import { IncidentDrawer } from "../components/IncidentDrawer";
import { IncidentTable } from "../components/IncidentTable";
import { useApp } from "../hooks/store";

export default function IncidentsPage() {
  const [selected, setSelected] = useState<number | null>(null);
  const { incidents } = useApp();
  const active = Object.values(incidents).filter((i) =>
    ["OPEN", "INVESTIGATING", "MITIGATING", "MONITORING"].includes(i.status),
  ).length;

  return (
    <div className="space-y-3 p-4">
      <div>
        <h1 className="text-lg font-semibold tracking-tight text-slate-100">Incident Center</h1>
        <p className="text-xs text-slate-500">
          {active} active · click any incident to inspect the full agent execution trace
        </p>
      </div>
      <IncidentTable limit={60} onSelect={setSelected} title="All Incidents" />
      <IncidentDrawer incidentId={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
