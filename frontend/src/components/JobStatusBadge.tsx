// Plan 21-10 Task 3 — per-row status badge for the Jobs list (FE-09
// row-level polling).
//
// Behavior:
//   * initialStatus in {succeeded, failed, cancelled} -> render a static
//     Badge. No useJob subscription, no polling. Terminal rows in a busy
//     list therefore cost zero requests (a static list of 50 succeeded
//     jobs fires exactly one GET /jobs list call).
//   * initialStatus in {queued, running}            -> mount <PollingBadge/>
//     which subscribes to useJob. The hook's refetchInterval returns 1s
//     while non-terminal and false once terminal (see useJob.ts); so this
//     row updates in place at 1 Hz and then stops. No explicit cleanup
//     needed — TanStack Query disposes the subscription on unmount.
//
// The initialStatus-based early return is stable per row: a row that
// starts non-terminal stays on the polling path for its lifetime; a row
// that starts terminal never mounts useJob. This keeps the React Rules
// of Hooks invariant satisfied — hooks inside PollingBadge are always
// the same count every render.
//
// Security (21-04 T-2): status text rendered as JSX children -> escaped
// by React. No dangerouslySetInnerHTML.
import { Badge } from "@/components/ui/badge";
import { isTerminalStatus, type JobDetail } from "@/api/client";
import { useJob } from "@/hooks/useJob";

type JobStatus = JobDetail["status"];

interface JobStatusBadgeProps {
  jobId: string;
  initialStatus: JobStatus;
}

function variantFor(
  status: JobStatus,
): "default" | "secondary" | "destructive" {
  if (status === "failed") return "destructive";
  if (status === "cancelled") return "secondary";
  return "default";
}

export function JobStatusBadge({ jobId, initialStatus }: JobStatusBadgeProps) {
  // Static path — terminal rows never hit the network from this component.
  if (isTerminalStatus(initialStatus)) {
    return <Badge variant={variantFor(initialStatus)}>{initialStatus}</Badge>;
  }
  // Non-terminal: delegate to the polling variant. Mounting PollingBadge
  // is the first useJob call on this jobId — TanStack Query dedupes across
  // concurrent subscribers (e.g. if the user opens the status page for the
  // same job in another tab) via the ["job", id] query key.
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
  // data is undefined while the first request is in flight; fall back to
  // the initialStatus snapshot so the user doesn't see a flash of nothing.
  const status = data?.status ?? fallback;
  return <Badge variant={variantFor(status)}>{status}</Badge>;
}
