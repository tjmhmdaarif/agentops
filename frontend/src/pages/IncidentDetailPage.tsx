import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { IncidentDetail } from "../components/IncidentDrawer";
import { Panel } from "../components/primitives";

export default function IncidentDetailPage() {
  const { id = "0" } = useParams();
  const incidentId = Number(id);
  return (
    <div className="p-4">
      <div className="mb-3 flex items-center gap-3">
        <Link to="/incidents" className="btn" aria-label="Back to incidents">
          <ArrowLeft className="h-3.5 w-3.5" />
        </Link>
        <h1 className="text-lg font-semibold tracking-tight text-slate-100">Incident Detail</h1>
      </div>
      <Panel pad={false} className="mx-auto max-w-3xl">
        {Number.isFinite(incidentId) && incidentId > 0 ? (
          <IncidentDetail incidentId={incidentId} />
        ) : (
          <p className="p-6 text-center text-xs text-slate-500">Invalid incident id.</p>
        )}
      </Panel>
    </div>
  );
}
