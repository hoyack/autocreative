// Single source of truth for "show a job's status, then its result".
//
//   queued    -> spinner + "Waiting in queue..."
//   running   -> spinner + elapsed time (live, 1s tick)
//   succeeded -> RenderPreview(s) from result_ref (string OR ResultLink[])
//   failed    -> destructive badge + JSON-serialized error_detail in a <pre>
//   cancelled -> secondary badge + short "cancelled" note
//
// Security (21-04-PLAN.md <threat_model> T-2): every server-derived string
// (job.kind, error_detail) is rendered as JSX text children — escaped by
// React. No raw-HTML injection.
import { useEffect, useState } from "react";
import { useJob } from "@/hooks/useJob";
import { RenderPreview } from "@/components/RenderPreview";
import { JobStatusBadge } from "@/components/JobStatusBadge";
import { formatElapsed } from "@/lib/elapsed";

interface JobStatusCardProps {
  jobId: string;
  title?: string;
}

export function JobStatusCard({ jobId, title }: JobStatusCardProps) {
  const { data: job, isPending, error } = useJob(jobId);

  const [now, setNow] = useState<number>(() => Date.now());
  useEffect(() => {
    if (!job || job.status !== "running") return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.status]);

  if (isPending) {
    return (
      <div className="border-t border-border pt-6 font-mono text-xs uppercase tracking-widest text-muted-foreground">
        Loading…
      </div>
    );
  }
  if (error) {
    return (
      <div className="border-l-2 border-destructive bg-destructive/5 p-5 font-mono text-sm text-destructive">
        Failed to load job:{" "}
        {error instanceof Error ? error.message : "unknown error"}
      </div>
    );
  }
  if (!job) return null;

  const startedMs = job.started_at ? new Date(job.started_at).getTime() : null;
  const completedMs = job.completed_at
    ? new Date(job.completed_at).getTime()
    : null;
  const elapsedMs = startedMs == null ? 0 : (completedMs ?? now) - startedMs;
  const kindLabel = job.kind.replace(/_/g, " ");

  return (
    <article className="border-t border-foreground/90">
      <header className="flex flex-wrap items-baseline justify-between gap-4 py-6">
        <div className="flex items-baseline gap-6">
          <span className="kicker">{title ?? "Job"}</span>
          <h2
            className="font-display text-3xl italic leading-none tracking-tight text-foreground"
            style={{
              fontVariationSettings: '"opsz" 144, "SOFT" 60, "WONK" 1',
            }}
          >
            {kindLabel}
          </h2>
          <JobStatusBadge jobId={job.id} initialStatus={job.status} />
        </div>
        {job.status === "running" && startedMs != null && (
          <div className="font-mono text-[11px] tabular-nums uppercase tracking-[0.16em] text-muted-foreground">
            Elapsed ·{" "}
            <span className="text-amber-deep">{formatElapsed(elapsedMs)}</span>
          </div>
        )}
      </header>

      <div className="border-t border-border pt-6 pb-10">
        {job.status === "queued" && (
          <div className="flex items-baseline gap-4 font-display text-xl italic text-muted-foreground">
            <span
              aria-hidden
              className="h-1.5 w-1.5 rounded-full bg-amber animate-pulse"
            />
            Waiting in queue…
          </div>
        )}

        {job.status === "running" && (
          <div className="flex items-baseline gap-4 font-display text-xl italic text-muted-foreground">
            <span
              aria-hidden
              className="h-1.5 w-1.5 rounded-full bg-amber animate-pulse"
            />
            Generating… {formatElapsed(elapsedMs)} elapsed.
          </div>
        )}

        {job.status === "succeeded" &&
          typeof job.result_ref === "string" && (
            <RenderPreview
              url={job.result_ref}
              alt={`${job.kind} render`}
            />
          )}

        {job.status === "succeeded" && Array.isArray(job.result_ref) && (
          <div className="grid gap-10 sm:grid-cols-2 md:grid-cols-3">
            {job.result_ref.map((link) => (
              <figure key={link.platform} className="space-y-3">
                <figcaption className="kicker">{link.platform}</figcaption>
                <RenderPreview
                  url={link.url}
                  alt={`${link.platform} render`}
                />
              </figure>
            ))}
          </div>
        )}

        {job.status === "failed" && job.error_detail && (
          <div className="border-l-2 border-destructive bg-destructive/5 p-5">
            <div className="kicker mb-3 text-destructive">Error detail</div>
            <pre className="overflow-x-auto font-mono text-xs leading-relaxed text-foreground/85">
              {JSON.stringify(job.error_detail, null, 2)}
            </pre>
          </div>
        )}

        {job.status === "cancelled" && (
          <p className="font-display text-xl italic text-muted-foreground">
            This job was cancelled.
          </p>
        )}
      </div>
    </article>
  );
}
