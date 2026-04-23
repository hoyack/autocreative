// Single source of truth for "show a job's status, then its result".
//
// Per 21-RESEARCH.md Pattern 3 consumer (lines 762-797) + 21-CONTEXT.md
// "Job Polling UX" (lines 76-80):
//
//   queued    -> spinner + "Waiting in queue..."
//   running   -> spinner + elapsed time (live, 1s tick)
//   succeeded -> RenderPreview(s) from result_ref (string OR ResultLink[])
//   failed    -> destructive badge + JSON-serialized error_detail in a <pre>
//   cancelled -> secondary badge + short "cancelled" note
//
// Every status page in plans 21-06..09 renders this component. Brochures
// (plan 21-07) wrap it with a second fetch for the 3-artifact BrochureDetail
// — that's out of scope for this file.
//
// Security (21-04-PLAN.md <threat_model> T-2): every server-derived string
// (job.kind, error_detail) is rendered as JSX text children and therefore
// escaped by React. No raw-HTML injection points exist in this file.
import { useEffect, useState } from "react";
import { useJob } from "@/hooks/useJob";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { RenderPreview } from "@/components/RenderPreview";
import { formatElapsed } from "@/lib/elapsed";

interface JobStatusCardProps {
  jobId: string;
  title?: string;
}

export function JobStatusCard({ jobId, title }: JobStatusCardProps) {
  const { data: job, isPending, error } = useJob(jobId);

  // Live-update elapsed time only while the job is actively running.
  const [now, setNow] = useState<number>(() => Date.now());
  useEffect(() => {
    if (!job || job.status !== "running") return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [job?.status]);

  if (isPending) return <Skeleton className="h-64 w-full" />;
  if (error) {
    return (
      <Card>
        <CardContent className="p-4 text-sm text-destructive">
          Failed to load job:{" "}
          {error instanceof Error ? error.message : "unknown error"}
        </CardContent>
      </Card>
    );
  }
  if (!job) return null;

  const startedMs = job.started_at
    ? new Date(job.started_at).getTime()
    : null;
  const completedMs = job.completed_at
    ? new Date(job.completed_at).getTime()
    : null;
  const elapsedMs =
    startedMs == null ? 0 : (completedMs ?? now) - startedMs;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <span>{title ?? job.kind}</span>
          <Badge
            variant={
              job.status === "failed"
                ? "destructive"
                : job.status === "cancelled"
                  ? "secondary"
                  : "default"
            }
          >
            {job.status}
          </Badge>
          {job.status === "running" && (
            <span className="text-sm text-muted-foreground">
              {formatElapsed(elapsedMs)}
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {job.status === "queued" && (
          <p className="text-sm text-muted-foreground">
            Waiting in queue...
          </p>
        )}
        {job.status === "running" && (
          <p className="text-sm text-muted-foreground">
            Generating... ({formatElapsed(elapsedMs)} elapsed)
          </p>
        )}
        {job.status === "succeeded" &&
          typeof job.result_ref === "string" && (
            <RenderPreview
              url={job.result_ref}
              alt={`${job.kind} render`}
            />
          )}
        {job.status === "succeeded" && Array.isArray(job.result_ref) && (
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
            {job.result_ref.map((link) => (
              <div key={link.platform} className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground">
                  {link.platform}
                </p>
                <RenderPreview
                  url={link.url}
                  alt={`${link.platform} render`}
                />
              </div>
            ))}
          </div>
        )}
        {job.status === "failed" && job.error_detail && (
          <pre className="overflow-x-auto rounded bg-muted p-4 text-xs">
            {JSON.stringify(job.error_detail, null, 2)}
          </pre>
        )}
        {job.status === "cancelled" && (
          <p className="text-sm text-muted-foreground">
            This job was cancelled.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
