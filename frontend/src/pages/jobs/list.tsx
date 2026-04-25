// Plan 21-10 Task 2 — replaces the plan-21-03 stub.
//
// Jobs list page (FE-09): paginated table of all jobs, newest-first, with
// kind + status filter dropdowns and click-through to each creative's
// status page.
//
// Security (21-04 T-2 + 21-10 threat model T-2): every server string
// (job.id, job.kind, job.status) is rendered as JSX children -> React
// escapes. No dangerouslySetInnerHTML anywhere.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { client } from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";
import { PageHeader } from "@/components/PageHeader";
import { JobStatusBadge } from "@/components/JobStatusBadge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";

// Phase 22 FT-08 (jobs half): intentionally unchanged from Phase 21. The
// flyer subtype split is RenderKind-level (flyer_event_final / flyer_info_final
// — see frontend/src/pages/renders/gallery.tsx::KINDS), NOT JobKind-level. The
// worker's JobRecord.kind stays "flyer" for both event and info subtypes
// because both go through the same task_generate_flyer handler. The
// statusPathFor() switch below routes both back to /flyers/:id; the flyer
// status page handles whichever subtype the render ends up being.
const KINDS = [
  "brand_kit",
  "flyer",
  "brochure",
  "social_post",
  "social_campaign",
] as const;
const STATUSES = [
  "queued",
  "running",
  "succeeded",
  "failed",
  "cancelled",
] as const;

function statusPathFor(kind: string, id: string): string {
  switch (kind) {
    case "flyer":
      return `/flyers/${id}`;
    case "brochure":
      return `/brochures/${id}`;
    case "social_post":
      return `/social/posts/${id}`;
    case "social_campaign":
      return `/social/campaigns/${id}`;
    case "brand_kit":
    default:
      return `/jobs/${id}`;
  }
}

const filterTriggerClasses =
  "h-10 rounded-none border-0 border-b border-border bg-transparent px-0 font-mono text-xs uppercase tracking-[0.14em] shadow-none focus:border-amber focus-visible:ring-0";

export function JobsListPage() {
  const [kind, setKind] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const { data, isPending, error } = useQuery({
    queryKey: queryKeys.jobs({ kind, status, limit, offset }),
    queryFn: async () => {
      const query: Record<string, unknown> = { limit, offset };
      if (kind) query.kind = kind;
      if (status) query.status = status;
      const { data, error } = await client.GET("/api/v1/jobs", {
        params: { query },
      });
      if (error || !data) throw new Error("failed to load jobs");
      return data;
    },
    refetchInterval: 60_000,
  });

  return (
    <div className="mx-auto max-w-screen-2xl px-10 pt-14 pb-24 md:px-14">
      <PageHeader
        number="06"
        kicker="The Queue"
        title="Jobs"
        dek="A ledger of every render the pipeline has queued, run, or shipped. Non-terminal rows poll every second."
      />

      <div className="mb-10 flex flex-wrap items-end gap-10 border-b border-border pb-6">
        <div className="min-w-[180px]">
          <div className="kicker mb-2">Kind</div>
          <Select
            value={kind || "all"}
            onValueChange={(v) => {
              setOffset(0);
              setKind(v === "all" ? "" : v);
            }}
          >
            <SelectTrigger className={filterTriggerClasses}>
              <SelectValue placeholder="All" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              {KINDS.map((k) => (
                <SelectItem key={k} value={k}>
                  {k}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="min-w-[180px]">
          <div className="kicker mb-2">Status</div>
          <Select
            value={status || "all"}
            onValueChange={(v) => {
              setOffset(0);
              setStatus(v === "all" ? "" : v);
            }}
          >
            <SelectTrigger className={filterTriggerClasses}>
              <SelectValue placeholder="All" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              {STATUSES.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {isPending ? (
        <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Loading…
        </p>
      ) : error ? (
        <p className="font-mono text-sm text-destructive">
          Failed: {(error as Error).message}
        </p>
      ) : (
        <>
          {data && data.items.length === 0 ? (
            <div className="border-t border-border py-24 text-center">
              <p className="font-display text-2xl italic text-muted-foreground">
                The queue is empty.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-y border-foreground/80 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                    <th className="py-3 pr-8 text-left font-medium">Created</th>
                    <th className="py-3 pr-8 text-left font-medium">Kind</th>
                    <th className="py-3 pr-8 text-left font-medium">Status</th>
                    <th className="py-3 text-left font-medium">Id</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.items.map((job) => (
                    <tr
                      key={job.id}
                      className="group border-b border-border/70 transition-colors hover:bg-card"
                    >
                      <td className="py-4 pr-8 font-mono text-xs tabular-nums text-foreground/85">
                        {new Date(job.created_at).toLocaleString("en-US", {
                          month: "short",
                          day: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                      <td className="py-4 pr-8 font-display text-base italic text-foreground/90">
                        {job.kind.replace(/_/g, " ")}
                      </td>
                      <td className="py-4 pr-8">
                        <JobStatusBadge
                          jobId={job.id}
                          initialStatus={job.status}
                        />
                      </td>
                      <td className="py-4 font-mono text-xs">
                        <Link
                          to={statusPathFor(job.kind, job.id)}
                          className="tabular-nums text-foreground/70 transition-colors hover:text-amber"
                        >
                          {job.id.slice(0, 14)}…
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {data && data.total > limit && (
            <div className="mt-10 flex items-center justify-between border-t border-border pt-6">
              <Button
                variant="ghost"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - limit))}
                className="h-9 rounded-none font-mono text-[11px] uppercase tracking-[0.18em]"
              >
                ← Previous
              </Button>
              <span className="font-mono text-[11px] tabular-nums uppercase tracking-widest text-muted-foreground">
                {offset + 1}–{Math.min(offset + data.items.length, data.total)}{" "}
                / {data.total}
              </span>
              <Button
                variant="ghost"
                disabled={offset + limit >= data.total}
                onClick={() => setOffset(offset + limit)}
                className="h-9 rounded-none font-mono text-[11px] uppercase tracking-[0.18em]"
              >
                Next →
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
