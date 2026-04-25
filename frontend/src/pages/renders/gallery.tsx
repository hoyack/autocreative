// Plan 21-11 Task 2 — replaces the plan-21-03 stub.
// Plan 24.2-02 — adds per-card delete (Trash2 + AlertDialog + optimistic mutation).
//
// Renders gallery (FE-10): a CSS-grid of RenderCard items. Editorial restyle:
// oversized thumbnails in tall frames, numbered overlay, mono metadata,
// thin rule separators. PDF items show a typographic download link.
//
// Security (plan threat model T-2 / T-4): every server-supplied string
// (r.id, r.kind, r.created_at) is rendered as JSX children — React escapes.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";

import { type ApiErrorBody, client } from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { RenderPreview } from "@/components/RenderPreview";
import { PageHeader } from "@/components/PageHeader";

// Phase 22 FT-08 (gallery half): "flyer_final" was split into subtype-derived
// kinds. The worker now emits "flyer_event_final" (subtype === "event") or
// "flyer_info_final" (subtype === "info"); pre-Phase-22 rows are migrated
// in-place by alembic f22t01. The legacy "flyer_final" value MUST NOT appear
// in this tuple — it would surface a filter that returns 0 rows post-migration.
//
// Phase 23 PC-06 adds postcard_front / postcard_back / postcard_pdf — same
// 3-artifact shape as brochures (front PNG + back PNG + print PDF), emitted
// by task_generate_postcard.
//
// Phase 24 PO-04 adds poster_final — single-artifact (1 PNG, no front/back/pdf
// split) emitted by task_generate_poster at print canvas dims (5400x7200,
// 7200x10800, or 8100x12000 depending on the locked size literal).
const KINDS = [
  "flyer_event_final",
  "flyer_info_final",
  "brochure_front",
  "brochure_back",
  "brochure_pdf",
  "postcard_front",
  "postcard_back",
  "postcard_pdf",
  "poster_final",
  "social_post_image",
  "brand_kit_logo",
] as const;

function previewUrlFor(id: string): string {
  return `/api/v1/renders/${id}/image`;
}

function isPdfKind(kind: string): boolean {
  return kind.endsWith("_pdf");
}

export function RenderGalleryPage() {
  const [kind, setKind] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const limit = 24;

  const queryClient = useQueryClient();
  const queryKey = queryKeys.renders({ kind, limit, offset });

  const { data, isPending, error } = useQuery({
    queryKey,
    queryFn: async () => {
      const query: Record<string, unknown> = { limit, offset };
      if (kind) query.kind = kind;
      const { data, error } = await client.GET("/api/v1/renders", {
        params: { query },
      });
      if (error || !data) throw new Error("failed to load renders");
      return data;
    },
  });

  // Plan 24.2-02 — render delete with optimistic update + rollback.
  // The mutation:
  //   onMutate     -> cancel in-flight queries; snapshot current page;
  //                   filter the deleted card out of the cache.
  //   onError      -> restore the snapshot; surface error toast.
  //   onSuccess    -> invalidate queryKeys.renders() (every paginated/filtered
  //                   variant) so the next refetch confirms the deletion;
  //                   surface a small success toast.
  // The DELETE signature is auto-derived by openapi-fetch from schema.gen.ts.
  type RenderListData = NonNullable<typeof data>;
  const deleteMutation = useMutation<
    void,
    Error,
    string,
    { previous: RenderListData | undefined }
  >({
    mutationFn: async (renderId: string) => {
      const { error, response } = await client.DELETE(
        "/api/v1/renders/{render_id}",
        { params: { path: { render_id: renderId } } },
      );
      if (error) {
        const e = error as ApiErrorBody;
        throw new Error(
          typeof e.detail === "string" ? e.detail : `HTTP ${response.status}`,
        );
      }
    },
    onMutate: async (renderId: string) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<RenderListData>(queryKey);
      if (previous) {
        queryClient.setQueryData<RenderListData>(queryKey, {
          ...previous,
          items: previous.items.filter((r) => r.id !== renderId),
          total: Math.max(0, previous.total - 1),
        });
      }
      return { previous };
    },
    onError: (err, _renderId, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(queryKey, ctx.previous);
      toast.error(err.message);
    },
    onSuccess: () => {
      toast.success("Render deleted");
      // Use the bare key form for prefix invalidation — every paginated /
      // filtered variant of the gallery refetches.
      queryClient.invalidateQueries({ queryKey: queryKeys.renders() });
    },
  });

  return (
    <div className="mx-auto max-w-screen-2xl px-10 pt-14 pb-24 md:px-14">
      <PageHeader
        number="07"
        kicker="The Archive"
        title="Renders"
        dek="Every flyer, brochure, post, and logo this pipeline has shipped — ordered newest to oldest, filterable by kind."
      />

      <div className="mb-10 flex flex-wrap items-end gap-10 border-b border-border pb-6">
        <div className="min-w-[220px]">
          <div className="kicker mb-2">Kind</div>
          <Select
            value={kind || "all"}
            onValueChange={(v) => {
              setOffset(0);
              setKind(v === "all" ? "" : v);
            }}
          >
            <SelectTrigger className="h-10 rounded-none border-0 border-b border-border bg-transparent px-0 font-mono text-xs uppercase tracking-[0.14em] shadow-none focus:border-amber focus-visible:ring-0">
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
      </div>

      {isPending ? (
        <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Loading…
        </p>
      ) : error ? (
        <p className="font-mono text-sm text-destructive">
          Failed: {(error as Error).message}
        </p>
      ) : data && data.items.length === 0 ? (
        <div className="border-t border-border py-24 text-center">
          <p className="font-display text-2xl italic text-muted-foreground">
            Archive is empty.
          </p>
        </div>
      ) : (
        <div className="grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {data?.items.map((r, i) => {
            const url = previewUrlFor(r.id);
            return (
              <figure key={r.id} className="group">
                <div className="relative aspect-[2/3] overflow-hidden bg-card">
                  {isPdfKind(r.kind) ? (
                    <a
                      href={url}
                      download={`${r.id}.pdf`}
                      className="absolute inset-0 flex flex-col items-center justify-center gap-3 border border-border transition-colors hover:border-amber"
                    >
                      <span
                        className="font-display text-6xl italic text-muted-foreground transition-colors group-hover:text-amber"
                        style={{
                          fontVariationSettings:
                            '"opsz" 144, "SOFT" 80, "WONK" 1',
                        }}
                      >
                        PDF
                      </span>
                      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                        Click to download →
                      </span>
                    </a>
                  ) : (
                    <RenderPreview url={url} alt={r.kind} />
                  )}
                  <span className="absolute top-3 left-3 font-mono text-[10px] tabular-nums tracking-widest text-muted-foreground mix-blend-multiply">
                    {String(offset + i + 1).padStart(3, "0")}
                  </span>
                  {/* Plan 24.2-02 — per-card delete trigger. Sits OUTSIDE the
                      PDF download <a> so the click never bubbles into the
                      anchor. AlertDialog handles its own focus + escape. */}
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label="Delete render"
                        className="absolute top-2 right-2 z-10 bg-background/70 hover:bg-background"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Delete render?</AlertDialogTitle>
                        <AlertDialogDescription>
                          This will permanently delete the file. Parent jobs,
                          brochures, and postcards keep their record but the
                          artifact will be gone. This cannot be undone.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                          onClick={() => deleteMutation.mutate(r.id)}
                          className={cn(
                            buttonVariants({ variant: "destructive" }),
                          )}
                        >
                          Delete
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
                <figcaption className="mt-4 border-t border-border pt-3 font-mono text-[10px] uppercase tracking-[0.14em] leading-relaxed text-muted-foreground">
                  <div className="text-foreground/85">
                    {r.kind.replace(/_/g, " ")}
                  </div>
                  <div className="mt-1 tabular-nums">
                    {new Date(r.created_at).toLocaleDateString("en-US", {
                      month: "short",
                      day: "2-digit",
                      year: "numeric",
                    })}
                  </div>
                </figcaption>
              </figure>
            );
          })}
        </div>
      )}

      {data && data.total > limit && (
        <div className="mt-16 flex items-center justify-between border-t border-border pt-6">
          <Button
            variant="ghost"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - limit))}
            className="h-9 rounded-none font-mono text-[11px] uppercase tracking-[0.18em]"
          >
            ← Previous
          </Button>
          <span className="font-mono text-[11px] tabular-nums uppercase tracking-widest text-muted-foreground">
            {offset + 1}–{Math.min(offset + data.items.length, data.total)} /{" "}
            {data.total}
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
    </div>
  );
}
