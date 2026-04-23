// Plan 21-10 Task 2 — replaces the plan-21-03 stub.
//
// Jobs list page (FE-09): paginated table of all jobs, newest-first, with
// kind + status filter dropdowns and click-through to each creative's
// status page.
//
// Per-row <JobStatusBadge> is the FE-09 row-level polling requirement:
// non-terminal rows subscribe to useJob and update in place every second;
// terminal rows render a static badge and cost zero per-row requests.
//
// List-level refresh: refetchInterval=60s picks up newly-enqueued jobs
// without hammering the server (list churn is slow). Per-row polling
// stays at 1s via JobStatusBadge -> useJob (plan 21-04 hook).
//
// Security (21-04 T-2 + 21-10 threat model T-2): every server string
// (job.id, job.kind, job.status) is rendered as JSX children -> React
// escapes. No dangerouslySetInnerHTML anywhere.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { client } from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { JobStatusBadge } from "@/components/JobStatusBadge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";

// Mirrors flyer_generator/api/models/job.py::JobKind + JobStatus. Keep in
// sync when the server-side enum grows a new variant.
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

/**
 * Map a JobKind onto the FE route that renders its per-creative status
 * page. brand_kit intentionally falls back to /jobs/:id — there is no
 * dedicated brand-kit status page today (a future plan can ship one
 * under /brand-kits/jobs/:id, at which point this switch gains a case).
 */
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
      // Brand-kit jobs + any future JobKind we haven't special-cased yet
      // route to the generic Jobs detail path (not yet implemented —
      // clicking this link lands on the wildcard NotFoundPage at /jobs/:id
      // which is an acceptable v1 fallback).
      return `/jobs/${id}`;
  }
}

export function JobsListPage() {
  const [kind, setKind] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const { data, isPending, error } = useQuery({
    queryKey: queryKeys.jobs({ kind, status, limit, offset }),
    queryFn: async () => {
      // Build the query object lazily so blank filters don't serialize as
      // "kind=" which FastAPI would 422 (empty string is not a valid enum).
      const query: Record<string, unknown> = { limit, offset };
      if (kind) query.kind = kind;
      if (status) query.status = status;
      const { data, error } = await client.GET("/api/v1/jobs", {
        params: { query },
      });
      if (error || !data) throw new Error("failed to load jobs");
      return data;
    },
    // List refresh cadence — 60s picks up newly-enqueued jobs without
    // being an annoying flicker. Per-row polling lives in JobStatusBadge.
    refetchInterval: 60_000,
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Jobs</h1>

      <div className="flex flex-wrap gap-3">
        <div className="min-w-[180px]">
          <label className="text-muted-foreground text-xs">Kind</label>
          <Select
            value={kind || "all"}
            onValueChange={(v) => {
              setOffset(0);
              setKind(v === "all" ? "" : v);
            }}
          >
            <SelectTrigger>
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
          <label className="text-muted-foreground text-xs">Status</label>
          <Select
            value={status || "all"}
            onValueChange={(v) => {
              setOffset(0);
              setStatus(v === "all" ? "" : v);
            }}
          >
            <SelectTrigger>
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

      {isPending && <Skeleton className="h-64 w-full" />}
      {error && (
        <p className="text-destructive">Failed: {(error as Error).message}</p>
      )}
      {data && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Created</TableHead>
                <TableHead>Kind</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Id</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={4}
                    className="text-muted-foreground text-center text-sm"
                  >
                    No jobs.
                  </TableCell>
                </TableRow>
              ) : (
                data.items.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell className="text-xs">
                      {new Date(job.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-xs">{job.kind}</TableCell>
                    <TableCell>
                      {/* Per-row <JobStatusBadge> — terminal rows render
                          statically; non-terminal rows poll /jobs/:id
                          every 1s via useJob (FE-09 row-level polling). */}
                      <JobStatusBadge
                        jobId={job.id}
                        initialStatus={job.status}
                      />
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      <Link
                        to={statusPathFor(job.kind, job.id)}
                        className="underline"
                      >
                        {job.id.slice(0, 12)}...
                      </Link>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
          {data.total > limit && (
            <div className="flex items-center justify-between">
              <Button
                variant="outline"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - limit))}
              >
                Previous
              </Button>
              <span className="text-muted-foreground text-sm">
                {offset + 1}&ndash;
                {Math.min(offset + data.items.length, data.total)} of{" "}
                {data.total}
              </span>
              <Button
                variant="outline"
                disabled={offset + limit >= data.total}
                onClick={() => setOffset(offset + limit)}
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
