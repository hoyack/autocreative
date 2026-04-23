import { Link } from "react-router";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { components } from "@/api/schema.gen";

type BrandKitSummary = components["schemas"]["BrandKitSummary"];

interface BrandKitCardProps {
  kit: BrandKitSummary;
}

/**
 * Card tile for a single brand kit. Clicking navigates to the detail page
 * /brand-kits/:slug. All text content is rendered as JSX children, so React
 * escapes scraped values (name, source_url) — no XSS (T-2 mitigation).
 */
export function BrandKitCard({ kit }: BrandKitCardProps) {
  return (
    <Link
      to={`/brand-kits/${encodeURIComponent(kit.slug)}`}
      className="block"
    >
      <Card className="hover:bg-muted/50 transition-colors">
        <CardHeader>
          <CardTitle>{kit.name ?? kit.slug}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <p className="text-muted-foreground font-mono text-xs">{kit.slug}</p>
          {kit.source_url && (
            <p className="text-muted-foreground truncate text-xs">
              {kit.source_url}
            </p>
          )}
          <p className="text-muted-foreground text-[10px]">
            scraped {new Date(kit.scraped_at).toLocaleDateString()}
          </p>
        </CardContent>
      </Card>
    </Link>
  );
}
