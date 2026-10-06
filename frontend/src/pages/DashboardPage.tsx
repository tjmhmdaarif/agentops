import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { ActivityFeed } from "../components/ActivityFeed";
import { FleetGrid } from "../components/FleetGrid";
import { IncidentDrawer } from "../components/IncidentDrawer";
import { IncidentTable } from "../components/IncidentTable";
import { KpiCards } from "../components/KpiCards";
import { LiveChart } from "../components/LiveChart";
import { EmptyState } from "../components/primitives";
import { useApp } from "../hooks/store";

export default function DashboardPage() {
  const { devices, deviceOrder, sim } = useApp();
  const [selectedIncident, setSelectedIncident] = useState<number | null>(null);

  return (
    <div className="space-y-3 p-4">
      {/* Compact hero strip */}
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-100">
            Autonomous Fleet Intelligence
          </h1>
          <p className="text-xs text-slate-500">
            Detect. Investigate. Remediate. — every action below is a real backend state transition.
          </p>
        </div>
        <Link to="/simulation" className="btn btn-primary">
          Run Demo Scenario <ArrowRight className="h-3 w-3" />
        </Link>
      </div>

      <KpiCards />

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
        <div className="space-y-3 xl:col-span-2">
          {deviceOrder.length === 0 ? (
            <EmptyState
              title="No devices yet"
              hint="The fleet initializes when the backend starts. Check the backend connection."
            />
          ) : sim?.status === "STOPPED" ? (
            <EmptyState
              title="Simulation stopped"
              hint="Start the simulation to begin receiving live telemetry."
              action={
                <Link to="/simulation" className="btn btn-primary mt-2">
                  Open Simulation Control
                </Link>
              }
            />
          ) : (
            <FleetGrid devices={devices} order={deviceOrder} />
          )}
        </div>
        <div className="min-h-[420px] xl:max-h-none">
          <ActivityFeed />
        </div>
      </div>

      <LiveChart />

      <IncidentTable onSelect={setSelectedIncident} />
      <IncidentDrawer incidentId={selectedIncident} onClose={() => setSelectedIncident(null)} />
    </div>
  );
}
