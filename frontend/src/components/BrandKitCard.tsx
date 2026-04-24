import { Link } from "react-router";

import type { components } from "@/api/schema.gen";

type BrandKitSummary = components["schemas"]["BrandKitSummary"];

interface BrandKitCardProps {
  kit: BrandKitSummary;
  index: number;
}

/**
 * Editorial tile for a single brand kit — thin top rule, oversized display
 * title in Fraunces, metadata set as mono key/value rows. React escapes all
 * scraped values (T-2 mitigation).
 */
export function BrandKitCard({ kit, index }: BrandKitCardProps) {
  const hostname = kit.source_url
    ? (() => {
        try {
          return new URL(kit.source_url).hostname.replace(/^www\./, "");
        } catch {
          return kit.source_url;
        }
      })()
    : null;

  return (
    <Link
      to={`/brand-kits/${encodeURIComponent(kit.slug)}`}
      className="group relative block border-t border-border pt-5 pb-6 transition-colors hover:border-amber"
    >
      <div className="flex items-start justify-between mb-4">
        <span className="font-mono text-[10px] tabular-nums tracking-widest text-muted-foreground">
          {String(index + 1).padStart(2, "0")}
        </span>
        <span
          aria-hidden
          className="h-1.5 w-1.5 rounded-full bg-border transition-colors group-hover:bg-amber"
        />
      </div>
      <h2
        className="font-display text-[28px] leading-[1.05] tracking-[-0.015em] text-foreground transition-colors group-hover:text-amber"
        style={{
          fontVariationSettings: '"opsz" 96, "SOFT" 40, "WONK" 0',
        }}
      >
        {kit.name ?? kit.slug}
      </h2>

      <dl className="mt-7 space-y-1.5 font-mono text-[11px] leading-relaxed">
        <div className="flex gap-3">
          <dt className="w-16 shrink-0 uppercase tracking-wider text-muted-foreground">
            Slug
          </dt>
          <dd className="text-foreground/85">{kit.slug}</dd>
        </div>
        {hostname && (
          <div className="flex gap-3">
            <dt className="w-16 shrink-0 uppercase tracking-wider text-muted-foreground">
              Source
            </dt>
            <dd className="truncate text-foreground/85">{hostname}</dd>
          </div>
        )}
        <div className="flex gap-3">
          <dt className="w-16 shrink-0 uppercase tracking-wider text-muted-foreground">
            Scraped
          </dt>
          <dd className="tabular-nums text-foreground/85">
            {new Date(kit.scraped_at).toLocaleDateString("en-US", {
              year: "numeric",
              month: "short",
              day: "2-digit",
            })}
          </dd>
        </div>
      </dl>
    </Link>
  );
}
