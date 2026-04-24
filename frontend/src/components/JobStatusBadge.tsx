// Plan 21-10 Task 3 — per-row status badge for the Jobs list (FE-09
// row-level polling). Editorial restyle: flat letterspaced mono pill with
// status-specific fill/stroke. React escapes all status strings (T-2).
import { isTerminalStatus, type JobDetail } from "@/api/client";
import { useJob } from "@/hooks/useJob";

type JobStatus = JobDetail["status"];

interface JobStatusBadgeProps {
  jobId: string;
  initialStatus: JobStatus;
}

const STATUS_STYLES: Record<JobStatus, string> = {
  queued:
    "border border-border bg-transparent text-foreground/75",
  running:
    "border border-amber bg-amber/15 text-amber-deep",
  succeeded:
    "border border-foreground bg-foreground text-background",
  failed:
    "border border-destructive bg-destructive text-background",
  cancelled:
    "border border-border bg-transparent text-muted-foreground",
};

const DOT_STYLES: Record<JobStatus, string> = {
  queued: "bg-foreground/35",
  running: "bg-amber animate-pulse",
  succeeded: "bg-background/70",
  failed: "bg-background/70",
  cancelled: "bg-foreground/35",
};

function StatusPill({ status }: { status: JobStatus }) {
  return (
    <span
      className={[
        "inline-flex items-center gap-2 px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.16em] leading-none",
        STATUS_STYLES[status],
      ].join(" ")}
    >
      <span
        aria-hidden
        className={["h-1.5 w-1.5 rounded-full", DOT_STYLES[status]].join(" ")}
      />
      {status}
    </span>
  );
}

export function JobStatusBadge({ jobId, initialStatus }: JobStatusBadgeProps) {
  if (isTerminalStatus(initialStatus)) {
    return <StatusPill status={initialStatus} />;
  }
  return <PollingBadge jobId={jobId} fallback={initialStatus} />;
}

function PollingBadge({
  jobId,
  fallback,
}: {
  jobId: string;
  fallback: JobStatus;
}) {
  const { data } = useJob(jobId);
  const status = data?.status ?? fallback;
  return <StatusPill status={status} />;
}
