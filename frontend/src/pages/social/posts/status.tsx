// Plan 21-08 Task 1 — replaces the plan-21-03 stub.
//
// Thin wrapper around <JobStatusCard/> (plan 21-04). All polling, status
// states, and render preview logic live inside JobStatusCard so this page
// stays minimal. Mirrors the 21-06 flyer status page pattern verbatim.
//
// v1 scope note: PostRecord.audit_report and validation_report are NOT
// exposed via the public API in Phase 20. The rendered post image is
// shown above (JobStatusCard -> RenderPreview when job.status ===
// "succeeded"). A future polish plan would add a dedicated read route
// for the audit/validation JSON and render it here.
import { Link, useParams } from "react-router";

import { JobStatusCard } from "@/components/JobStatusCard";

export function SocialPostStatusPage() {
  const { id = "" } = useParams<{ id: string }>();
  return (
    <div className="space-y-4">
      <Link to="/social/posts/new" className="text-sm underline">
        &larr; New post
      </Link>
      <h1 className="text-2xl font-semibold">Social post job</h1>
      <JobStatusCard jobId={id} title="Social post" />
      <p className="text-muted-foreground text-xs">
        Note: validation report + audit report are not exposed via the
        public API in v1. The rendered image is shown above when the job
        succeeds.
      </p>
    </div>
  );
}
