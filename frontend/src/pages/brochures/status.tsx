// Plan 21-07 Task 2 — brochure status page.
//
// Polls the job via <JobStatusCard/>; once succeeded, additionally GETs
// /api/v1/brochures/{id} and renders the 3 artifacts (front PNG, back
// PNG, print PDF) via <RenderPreview/>.
import { Link, useParams } from "react-router";
import { useQuery } from "@tanstack/react-query";

import { JobStatusCard } from "@/components/JobStatusCard";
import { RenderPreview } from "@/components/RenderPreview";
import { useJob } from "@/hooks/useJob";
import { client } from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";

export function BrochureStatusPage() {
  const { id = "" } = useParams<{ id: string }>();
  const { data: job } = useJob(id);

  const { data: detail, isPending: detailPending } = useQuery({
    queryKey: queryKeys.brochure(id),
    enabled: job?.status === "succeeded",
    queryFn: async () => {
      const { data, error } = await client.GET(
        "/api/v1/brochures/{brochure_id}",
        { params: { path: { brochure_id: id } } },
      );
      if (error || !data) throw new Error("brochure not found");
      return data;
    },
  });

  return (
    <div className="mx-auto max-w-screen-xl px-10 pt-14 pb-24 md:px-14">
      <Link
        to="/brochures/new"
        className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground hover:text-amber"
      >
        <span aria-hidden>←</span>
        New brochure
      </Link>
      <div className="mt-6">
        <div className="font-mono text-[11px] tracking-[0.2em] uppercase text-muted-foreground">
          <span className="text-amber">03</span>
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
          Brochure job
        </h1>
      </div>

      <div className="mt-10">
        <JobStatusCard jobId={id} title="Brochure" />
      </div>

      {job?.status === "succeeded" && (
        <section className="mt-16 border-t border-foreground/80 pt-6">
          <div className="flex items-baseline gap-4 pb-8">
            <span className="kicker">Artifacts</span>
            <h2
              className="font-display text-3xl italic leading-none tracking-tight text-foreground"
              style={{
                fontVariationSettings: '"opsz" 144, "SOFT" 60, "WONK" 1',
              }}
            >
              three panels
            </h2>
          </div>

          {detailPending && (
            <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
              Loading detail…
            </p>
          )}

          <div className="grid gap-10 md:grid-cols-3">
            {detail?.front_render_url && (
              <figure className="space-y-3">
                <figcaption className="kicker">Front · PNG</figcaption>
                <RenderPreview
                  url={detail.front_render_url}
                  alt="Brochure front"
                />
              </figure>
            )}
            {detail?.back_render_url && (
              <figure className="space-y-3">
                <figcaption className="kicker">Back · PNG</figcaption>
                <RenderPreview
                  url={detail.back_render_url}
                  alt="Brochure back"
                />
              </figure>
            )}
            {detail?.pdf_render_url && (
              <figure className="space-y-3">
                <figcaption className="kicker">Print · PDF</figcaption>
                <RenderPreview
                  url={detail.pdf_render_url}
                  alt="Brochure PDF"
                  isPdf
                />
              </figure>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
