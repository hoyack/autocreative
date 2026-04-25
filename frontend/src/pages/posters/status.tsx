// Plan 24-05 Task 1 — poster status page (PO-04).
//
// Single-artifact, so this page is a thin wrapper around <JobStatusCard />
// per CONTEXT.md D-XX. JobStatusCard already handles polling + rendering
// the result_ref artifact (the /api/v1/renders/{id}/image URL); no
// GET /posters/{id} fetch is needed (no detail route exists — locked
// decision in 24-CONTEXT.md and 24-04 worker SUMMARY).
//
// Header block mirrors brochures/postcards manual h1 + back-link, but
// without the "three panels" artifact grid because posters ship only one
// PNG.
import { Link, useParams } from "react-router";
import { JobStatusCard } from "@/components/JobStatusCard";

export function PosterStatusPage() {
  const { id = "" } = useParams<{ id: string }>();

  return (
    <div className="mx-auto max-w-screen-xl px-10 pt-14 pb-24 md:px-14">
      <Link
        to="/posters/new"
        className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground hover:text-amber"
      >
        <span aria-hidden>←</span>
        New poster
      </Link>
      <div className="mt-6">
        <div className="font-mono text-[11px] tracking-[0.2em] uppercase text-muted-foreground">
          <span className="text-amber">09</span>
          <span aria-hidden className="mx-3">
            /
          </span>
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
          Poster job
        </h1>
      </div>

      <div className="mt-10">
        <JobStatusCard jobId={id} title="Poster" />
      </div>
    </div>
  );
}
