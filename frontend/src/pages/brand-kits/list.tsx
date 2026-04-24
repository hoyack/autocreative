import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { client } from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";
import { BrandKitCard } from "@/components/BrandKitCard";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";

export function BrandKitsListPage() {
  const [offset, setOffset] = useState(0);
  const limit = 24;

  const { data, isPending, error } = useQuery({
    queryKey: queryKeys.brandKits({ limit, offset }),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/brand-kits", {
        params: { query: { limit, offset } },
      });
      if (error || !data) throw new Error("failed to load brand kits");
      return data;
    },
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="mx-auto max-w-screen-2xl px-10 pt-14 pb-24 md:px-14">
      <PageHeader
        number="01"
        kicker="The Index"
        title="Brand kits"
        dek="Scraped identity systems — palette, typography, voice, and logo set — ready to condition every render."
        actions={
          <Button
            asChild
            className="h-11 rounded-none bg-foreground px-6 font-mono text-[11px] uppercase tracking-[0.18em] text-background hover:bg-amber hover:text-background"
          >
            <Link to="/brand-kits/new">Add brand kit</Link>
          </Button>
        }
      />

      {isPending ? (
        <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Loading…
        </p>
      ) : error ? (
        <p className="font-mono text-sm text-destructive">
          Failed: {(error as Error).message}
        </p>
      ) : items.length === 0 ? (
        <div className="border-t border-border py-24 text-center">
          <p className="font-display text-2xl italic text-muted-foreground">
            No brand kits yet.
          </p>
          <p className="mt-4 font-mono text-xs uppercase tracking-widest text-muted-foreground">
            <Link
              to="/brand-kits/new"
              className="underline decoration-amber decoration-2 underline-offset-4 hover:text-amber"
            >
              Scrape one
            </Link>
          </p>
        </div>
      ) : (
        <div className="grid gap-x-10 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((kit, i) => (
            <BrandKitCard key={kit.slug} kit={kit} index={offset + i} />
          ))}
        </div>
      )}

      {total > limit && (
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
            {offset + 1}–{Math.min(offset + items.length, total)} / {total}
          </span>
          <Button
            variant="ghost"
            disabled={offset + limit >= total}
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
