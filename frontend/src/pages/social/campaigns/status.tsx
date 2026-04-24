// Plan 21-09 Task 1 — thin wrapper around <JobStatusCard/>.
// JobStatusCard handles the array-shaped result_ref via its per-platform grid.
import { Link, useParams } from "react-router";

import { JobStatusCard } from "@/components/JobStatusCard";

export function CampaignStatusPage() {
  const { id = "" } = useParams<{ id: string }>();
  return (
    <div className="mx-auto max-w-screen-xl px-10 pt-14 pb-24 md:px-14">
      <Link
        to="/social/campaigns/new"
        className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground hover:text-amber"
      >
        <span aria-hidden>←</span>
        New campaign
      </Link>
      <div className="mt-6">
        <div className="font-mono text-[11px] tracking-[0.2em] uppercase text-muted-foreground">
          <span className="text-amber">05</span>
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
          Campaign job
        </h1>
      </div>
      <div className="mt-10">
        <JobStatusCard jobId={id} title="Campaign" />
      </div>
    </div>
  );
}
