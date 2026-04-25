// Plan 23-05 Task 2 — postcard status page (PC-05).
//
// Polls the job via <JobStatusCard/>; once succeeded, additionally GETs
// /api/v1/postcards/{id} and renders the 3 artifacts (front PNG, back PNG,
// print PDF) via <RenderPreview/>. Mirrors brochures/status.tsx verbatim
// modulo strings (Brochure -> Postcard, "03" -> "08").
import { Link, useParams } from "react-router";
import { useQuery } from "@tanstack/react-query";

import { JobStatusCard } from "@/components/JobStatusCard";
import { RenderPreview } from "@/components/RenderPreview";
import { useJob } from "@/hooks/useJob";
import { client } from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";

export function PostcardStatusPage() {
  const { id = "" } = useParams<{ id: string }>();
  const { data: job } = useJob(id);

  const { data: detail, isPending: detailPending } = useQuery({
    queryKey: queryKeys.postcard(id),
    enabled: job?.status === "succeeded",
    queryFn: async () => {
      const { data, error } = await client.GET(
        "/api/v1/postcards/{postcard_id}",
        { params: { path: { postcard_id: id } } },
      );
      if (error || !data) throw new Error("postcard not found");
      return data;
    },
  });

  return (
    <div className="mx-auto max-w-screen-xl px-10 pt-14 pb-24 md:px-14">
      <Link
        to="/postcards/new"
        className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground hover:text-amber"
      >
        <span aria-hidden>←</span>
        New postcard
      </Link>
      <div className="mt-6">
        <div className="font-mono text-[11px] tracking-[0.2em] uppercase text-muted-foreground">
          <span className="text-amber">08</span>
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
          Postcard job
        </h1>
      </div>

      <div className="mt-10">
        <JobStatusCard jobId={id} title="Postcard" />
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
                  alt="Postcard front"
                />
              </figure>
            )}
            {detail?.back_render_url && (
              <figure className="space-y-3">
                <figcaption className="kicker">Back · PNG</figcaption>
                <RenderPreview
                  url={detail.back_render_url}
                  alt="Postcard back"
                />
              </figure>
            )}
            {detail?.pdf_render_url && (
              <figure className="space-y-3">
                <figcaption className="kicker">Print · PDF</figcaption>
                <RenderPreview
                  url={detail.pdf_render_url}
                  alt="Postcard PDF"
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
