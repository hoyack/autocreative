// Plan 21-05 Task 3 — replaces the plan-21-03 stub.
//
// Detail page for /brand-kits/:slug. Composes PaletteSwatches + LogoGallery
// + typography sample + voice into a single vertical stack. React escapes
// every scraped string (kit.name, voice.tone, etc.) — T-2 mitigation.
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { client } from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";
import { LogoGallery } from "@/components/LogoGallery";
import { PaletteSwatches } from "@/components/PaletteSwatches";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";

export function BrandKitDetailPage() {
  const { slug = "" } = useParams<{ slug: string }>();

  const { data, isPending, error } = useQuery({
    queryKey: queryKeys.brandKit(slug),
    queryFn: async () => {
      const { data, error } = await client.GET(
        "/api/v1/brand-kits/{slug}",
        {
          params: { path: { slug } },
        },
      );
      if (error || !data) throw new Error("brand kit not found");
      return data;
    },
    enabled: slug.length > 0,
  });

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (error) {
    return (
      <div className="space-y-3">
        <p className="text-destructive">{(error as Error).message}</p>
        <Link to="/brand-kits" className="text-sm underline">
          Back to brand kits
        </Link>
      </div>
    );
  }
  if (!data) return null;
  const kit = data.brand_kit;

  return (
    <div className="space-y-6">
      <div>
        <Link to="/brand-kits" className="text-sm underline">
          &larr; Brand kits
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">{kit.name ?? slug}</h1>
        {kit.source_url && (
          <p className="text-muted-foreground font-mono text-xs">
            {kit.source_url}
          </p>
        )}
      </div>

      {kit.palette && (
        <Card>
          <CardHeader>
            <CardTitle>Palette</CardTitle>
          </CardHeader>
          <CardContent>
            <PaletteSwatches palette={kit.palette} />
          </CardContent>
        </Card>
      )}

      {kit.typography && (
        <Card>
          <CardHeader>
            <CardTitle>Typography</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p>
              <span className="text-muted-foreground text-xs">Heading: </span>
              <span style={{ fontFamily: kit.typography.heading_family }}>
                {kit.typography.heading_family}
              </span>
            </p>
            <p>
              <span className="text-muted-foreground text-xs">Body: </span>
              <span style={{ fontFamily: kit.typography.body_family }}>
                {kit.typography.body_family}
              </span>
            </p>
            <p className="text-muted-foreground font-mono text-xs">
              Sizes:{" "}
              {Object.entries(kit.typography.size_scale ?? {})
                .map(([k, v]) => `${k}=${v}`)
                .join(", ")}
            </p>
          </CardContent>
        </Card>
      )}

      {kit.logos && kit.logos.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Logos</CardTitle>
          </CardHeader>
          <CardContent>
            <LogoGallery slug={slug} logos={kit.logos} />
          </CardContent>
        </Card>
      )}

      {kit.voice && (
        <Card>
          <CardHeader>
            <CardTitle>Voice</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>
              <span className="text-muted-foreground">Tone: </span>
              {kit.voice.tone}
            </p>
            {kit.voice.example_phrases &&
              kit.voice.example_phrases.length > 0 && (
                <div>
                  <span className="text-muted-foreground">
                    Example phrases:
                  </span>
                  <ul className="mt-1 list-disc pl-5">
                    {kit.voice.example_phrases.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}
            {kit.voice.banned_words &&
              kit.voice.banned_words.length > 0 && (
                <p>
                  <span className="text-muted-foreground">Banned: </span>
                  <span className="font-mono">
                    {kit.voice.banned_words.join(", ")}
                  </span>
                </p>
              )}
          </CardContent>
        </Card>
      )}

      <Separator />
      <div className="flex gap-2">
        <Link
          to={`/flyers/new?brand_kit=${encodeURIComponent(slug)}`}
          className="text-sm underline"
        >
          Use in a flyer
        </Link>
        <Link
          to={`/brochures/new?brand_kit=${encodeURIComponent(slug)}`}
          className="text-sm underline"
        >
          Use in a brochure
        </Link>
        <Link
          to={`/social/posts/new?brand_kit=${encodeURIComponent(slug)}`}
          className="text-sm underline"
        >
          Use in a post
        </Link>
      </div>
    </div>
  );
}
