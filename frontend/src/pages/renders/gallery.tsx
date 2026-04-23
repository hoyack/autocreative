// Plan 21-11 Task 2 — replaces the plan-21-03 stub.
//
// Renders gallery (FE-10): a CSS-grid of RenderCard items. Each card shows
// the render kind, a truncated id, created_at, and either an inline <img>
// (PNG / JPG) or a download <a> (PDF). Kind filter narrows the list; the
// Previous / Next pager handles offset-based pagination.
//
// Per 21-CONTEXT.md <specifics> "Render preview pattern" — PNG inline,
// PDF download. Per 21-PATTERNS.md "Backend addition: list_renders" the
// file bytes are NOT inlined in /api/v1/renders; we compute the preview URL
// client-side as /api/v1/renders/{id}/image (which flows through the
// existing streaming route with full T-1 path-containment defenses).
//
// Security (plan threat model T-2 / T-4): every server-supplied string
// (r.id, r.kind, r.created_at) is rendered as JSX children — React escapes.
// No dangerouslySetInnerHTML anywhere.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { client } from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { RenderPreview } from "@/components/RenderPreview";

// Valid RenderRecord.kind values (flyer_generator/api/models/render.py:23).
// Hard-coded; a schema-divergence would surface as a dropdown with a
// missing option + a 422 on submit (both obvious in manual testing).
const KINDS = [
  "flyer_final",
  "brochure_front",
  "brochure_back",
  "brochure_pdf",
  "social_post_image",
  "brand_kit_logo",
] as const;

/** Build the inline-stream URL for a render id. */
function previewUrlFor(id: string): string {
  return `/api/v1/renders/${id}/image`;
}

/**
 * PDF rendering is keyed off the RenderRecord.kind, not the URL suffix.
 * RenderPreview's URL-based ".pdf" detection would fail on our
 * /renders/{id}/image URL (no extension), so we branch on kind directly
 * and use <RenderPreview/> only for image kinds.
 */
function isPdfKind(kind: string): boolean {
  return kind.endsWith("_pdf");
}

export function RenderGalleryPage() {
  const [kind, setKind] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const limit = 24;

  const { data, isPending, error } = useQuery({
    queryKey: queryKeys.renders({ kind, limit, offset }),
    queryFn: async () => {
      // Blank-filter elision (plan 21-10 Rule 2 pattern): only include
      // ``kind`` in the query object when non-empty, so toggling back to
      // "All" never serializes ``?kind=`` (which FastAPI accepts for a
      // str|None Query but is still cleaner to omit).
      const query: Record<string, unknown> = { limit, offset };
      if (kind) query.kind = kind;
      const { data, error } = await client.GET("/api/v1/renders", {
        params: { query },
      });
      if (error || !data) throw new Error("failed to load renders");
      return data;
    },
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Renders</h1>

      <div className="min-w-[220px]">
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

      {isPending && <Skeleton className="h-64 w-full" />}
      {error && (
        <p className="text-destructive">Failed: {(error as Error).message}</p>
      )}
      {data && data.items.length === 0 && (
        <p className="text-muted-foreground text-sm">No renders.</p>
      )}
      {data && data.items.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {data.items.map((r) => {
            const url = previewUrlFor(r.id);
            return (
              <Card key={r.id}>
                <CardHeader className="space-y-1 p-3">
                  <Badge variant="secondary" className="self-start text-xs">
                    {r.kind}
                  </Badge>
                  <p className="text-muted-foreground font-mono text-[10px]">
                    {r.id.slice(0, 14)}...
                  </p>
                  <p className="text-muted-foreground text-[10px]">
                    {new Date(r.created_at).toLocaleString()}
                  </p>
                </CardHeader>
                <CardContent className="p-3">
                  {isPdfKind(r.kind) ? (
                    <a
                      href={url}
                      download={`${r.id}.pdf`}
                      className="hover:bg-muted inline-flex items-center gap-2 rounded border px-3 py-2 text-sm"
                    >
                      Download PDF
                    </a>
                  ) : (
                    <RenderPreview url={url} alt={r.kind} />
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
      {data && data.total > limit && (
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
            {Math.min(offset + data.items.length, data.total)} of {data.total}
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
    </div>
  );
}
