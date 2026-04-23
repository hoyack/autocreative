// Plan 21-06 Task 1 — replaces the plan-21-03 stub.
//
// Thin wrapper around <JobStatusCard/> (plan 21-04). All polling, status
// states, and render preview logic live inside JobStatusCard so this page
// stays minimal.
import { Link, useParams } from "react-router";

import { JobStatusCard } from "@/components/JobStatusCard";

export function FlyerStatusPage() {
  const { id = "" } = useParams<{ id: string }>();
  return (
    <div className="space-y-4">
      <Link to="/flyers/new" className="text-sm underline">
        &larr; New flyer
      </Link>
      <h1 className="text-2xl font-semibold">Flyer job</h1>
      <JobStatusCard jobId={id} title="Flyer" />
    </div>
  );
}
