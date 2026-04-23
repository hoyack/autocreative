// Plan 21-07 Task 2 — replaces the plan-21-03 stub.
//
// Brochure status page: polls the job via <JobStatusCard/>; once the job
// reaches succeeded, additionally GETs /api/v1/brochures/{id} and renders
// the 3 artifacts (front PNG, back PNG, print PDF) via <RenderPreview/>.
//
// Per 21-07-PLAN.md Task 1 parallel-id pattern: the URL :id is the JobRecord.id
// which (after the Task 1 worker change) also equals BrochureRecord.id, so
// GET /brochures/{id} resolves directly. The job polls separately via useJob
// so the transitions queued -> running -> succeeded still display via the
// shared JobStatusCard.
import { Link, useParams } from "react-router";
import { useQuery } from "@tanstack/react-query";

import { JobStatusCard } from "@/components/JobStatusCard";
import { RenderPreview } from "@/components/RenderPreview";
import { useJob } from "@/hooks/useJob";
import { client } from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function BrochureStatusPage() {
  const { id = "" } = useParams<{ id: string }>();
  const { data: job } = useJob(id);

  // Only fetch BrochureDetail once the job has succeeded — until then the
  // BrochureRecord row does not exist (the worker writes it at the tail of
  // task_generate_brochure). `enabled` gates the query off until the
  // terminal-state transition fires.
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
    <div className="space-y-6">
      <Link to="/brochures/new" className="text-sm underline">
        &larr; New brochure
      </Link>
      <h1 className="text-2xl font-semibold">Brochure job</h1>

      {/* JobStatusCard polls while the job is non-terminal and also renders
          the default single-result-ref preview for non-brochure kinds. For
          brochure jobs the single preview is still correct (it's the front
          PNG's URL — the result_ref == BrochureRecord.id now resolves through
          the detail fetch below, not a direct render URL). */}
      <JobStatusCard jobId={id} title="Brochure" />

      {/* Once succeeded, render the 3-artifact view from BrochureDetail. */}
      {job?.status === "succeeded" && (
        <Card>
          <CardHeader>
            <CardTitle>Artifacts</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-3">
            {detailPending && (
              <Skeleton className="h-48 w-full md:col-span-3" />
            )}
            {detail?.front_render_url && (
              <div className="space-y-1">
                <p className="text-muted-foreground text-xs font-medium">
                  Front (PNG)
                </p>
                <RenderPreview
                  url={detail.front_render_url}
                  alt="Brochure front"
                />
              </div>
            )}
            {detail?.back_render_url && (
              <div className="space-y-1">
                <p className="text-muted-foreground text-xs font-medium">
                  Back (PNG)
                </p>
                <RenderPreview
                  url={detail.back_render_url}
                  alt="Brochure back"
                />
              </div>
            )}
            {detail?.pdf_render_url && (
              <div className="space-y-1">
                <p className="text-muted-foreground text-xs font-medium">
                  Print PDF
                </p>
                <RenderPreview
                  url={detail.pdf_render_url}
                  alt="Brochure PDF"
                  isPdf
                />
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
