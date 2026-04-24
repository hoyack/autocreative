// Plan 21-08 Task 1 — thin wrapper around <JobStatusCard/>.
import { Link, useParams } from "react-router";

import { JobStatusCard } from "@/components/JobStatusCard";

export function SocialPostStatusPage() {
  const { id = "" } = useParams<{ id: string }>();
  return (
    <div className="mx-auto max-w-screen-xl px-10 pt-14 pb-24 md:px-14">
      <Link
        to="/social/posts/new"
        className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground hover:text-amber"
      >
        <span aria-hidden>←</span>
        New post
      </Link>
      <div className="mt-6">
        <div className="font-mono text-[11px] tracking-[0.2em] uppercase text-muted-foreground">
          <span className="text-amber">04</span>
          <span aria-hidden className="mx-3">/</span>
          Job ·{" "}
          <span className="normal-case tracking-wider">
            {id.slice(0, 14)}…
          </span>
        </div>
        <h1
          className="mt-5 font-display text-5xl leading-[0.95] tracking-[-0.025em] text-foreground"
          style={{
            fontVariationSettings: '"opsz" 144, "SOFT" 40, "WONK" 0',
          }}
        >
          Social post job
        </h1>
      </div>
      <div className="mt-10">
        <JobStatusCard jobId={id} title="Social post" />
      </div>
      <p className="mt-10 border-t border-border pt-5 font-display text-sm italic text-muted-foreground">
        v1 scope — the validation + audit reports are not yet exposed via
        the public API. Only the rendered image is shown above when the job
        succeeds.
      </p>
    </div>
  );
}
