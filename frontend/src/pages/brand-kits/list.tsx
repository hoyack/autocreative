// Plan 21-05 Task 3 — replaces the plan-21-03 stub.
//
// Paginated list page for /brand-kits. Uses TanStack Query with the central
// queryKeys.brandKits({limit, offset}) registry entry.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { client } from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";
import { BrandKitCard } from "@/components/BrandKitCard";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

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

  if (isPending) return <Skeleton className="h-64 w-full" />;
  if (error) {
    return (
      <p className="text-destructive">
        Failed: {(error as Error).message}
      </p>
    );
  }
  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Brand kits</h1>
        <Button asChild>
          <Link to="/brand-kits/new">Add brand kit</Link>
        </Button>
      </div>

      {items.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No brand kits yet.{" "}
          <Link to="/brand-kits/new" className="underline">
            Scrape one
          </Link>
          .
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((kit) => (
            <BrandKitCard key={kit.slug} kit={kit} />
          ))}
        </div>
      )}

      {total > limit && (
        <div className="flex items-center justify-between">
          <Button
            variant="outline"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - limit))}
          >
            Previous
          </Button>
          <span className="text-muted-foreground text-sm">
            {offset + 1}&ndash;{Math.min(offset + items.length, total)} of{" "}
            {total}
          </span>
          <Button
            variant="outline"
            disabled={offset + limit >= total}
            onClick={() => setOffset(offset + limit)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
