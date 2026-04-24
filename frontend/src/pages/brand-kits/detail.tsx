// Plan 21-05 Task 3 — replaces the plan-21-03 stub.
//
// Detail page for /brand-kits/:slug. Editorial restyle: back-nav rail,
// magazine-spread masthead, sections as full-bleed horizontal rules with
// kicker + content blocks. React escapes every scraped string — T-2.
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { client } from "@/api/client";
import { queryKeys } from "@/lib/queryKeys";
import { LogoGallery } from "@/components/LogoGallery";
import { PaletteSwatches } from "@/components/PaletteSwatches";

interface SectionProps {
  number: string;
  title: string;
  children: React.ReactNode;
}

function Section({ number, title, children }: SectionProps) {
  return (
    <section className="grid gap-8 border-t border-border py-10 md:grid-cols-[180px_1fr]">
      <div>
        <div className="font-mono text-[10px] tabular-nums tracking-widest text-amber">
          {number}
        </div>
        <h2
          className="mt-3 font-display text-2xl italic leading-tight tracking-tight text-foreground"
          style={{
            fontVariationSettings: '"opsz" 96, "SOFT" 60, "WONK" 1',
          }}
        >
          {title}
        </h2>
      </div>
      <div className="min-w-0">{children}</div>
    </section>
  );
}

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

  if (isPending) {
    return (
      <div className="mx-auto max-w-screen-lg px-10 pt-14 md:px-14">
        <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Loading…
        </p>
      </div>
    );
  }
  if (error) {
    return (
      <div className="mx-auto max-w-screen-lg px-10 pt-14 md:px-14">
        <p className="font-display text-2xl italic text-destructive">
          {(error as Error).message}
        </p>
        <Link
          to="/brand-kits"
          className="mt-4 inline-block font-mono text-xs uppercase tracking-widest text-foreground underline decoration-amber decoration-2 underline-offset-4"
        >
          ← Back to brand kits
        </Link>
      </div>
    );
  }
  if (!data) return null;
  const kit = data.brand_kit;

  return (
    <div className="mx-auto max-w-screen-lg px-10 pt-14 pb-24 md:px-14">
      <Link
        to="/brand-kits"
        className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground hover:text-amber"
      >
        <span aria-hidden>←</span>
        Back to the index
      </Link>

      <header className="mt-8 mb-4">
        <div className="font-mono text-[11px] tracking-[0.2em] uppercase text-muted-foreground">
          <span className="text-amber">01</span>
          <span aria-hidden className="mx-3">/</span>
          Brand kit · {slug}
        </div>
        <h1
          className="mt-5 font-display text-6xl leading-[0.95] tracking-[-0.025em] text-foreground"
          style={{
            fontVariationSettings: '"opsz" 144, "SOFT" 40, "WONK" 0',
          }}
        >
          {kit.name ?? slug}
        </h1>
        {kit.source_url && (
          <a
            href={kit.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-4 inline-block font-mono text-xs tracking-wide text-muted-foreground hover:text-amber"
          >
            {kit.source_url} ↗
          </a>
        )}
      </header>

      <div className="mt-10">
        {kit.palette && (
          <Section number="I." title="Palette">
            <PaletteSwatches palette={kit.palette} />
          </Section>
        )}

        {kit.typography && (
          <Section number="II." title="Typography">
            <div className="space-y-6">
              <div>
                <div className="kicker mb-2">Heading family</div>
                <p
                  className="text-4xl leading-tight text-foreground"
                  style={{ fontFamily: kit.typography.heading_family }}
                >
                  {kit.typography.heading_family}
                </p>
              </div>
              <div>
                <div className="kicker mb-2">Body family</div>
                <p
                  className="text-lg leading-relaxed text-foreground/85"
                  style={{ fontFamily: kit.typography.body_family }}
                >
                  {kit.typography.body_family} — the quick brown fox jumps
                  over the lazy dog.
                </p>
              </div>
              <div>
                <div className="kicker mb-2">Scale</div>
                <div className="flex flex-wrap gap-x-8 gap-y-2 font-mono text-xs tabular-nums text-foreground/75">
                  {Object.entries(kit.typography.size_scale ?? {}).map(
                    ([k, v]) => (
                      <span key={k}>
                        <span className="text-muted-foreground">{k}</span>{" "}
                        {String(v)}
                      </span>
                    ),
                  )}
                </div>
              </div>
            </div>
          </Section>
        )}

        {kit.logos && kit.logos.length > 0 && (
          <Section number="III." title="Logos">
            <LogoGallery slug={slug} logos={kit.logos} />
          </Section>
        )}

        {kit.voice && (
          <Section number="IV." title="Voice">
            <dl className="space-y-5">
              <div>
                <dt className="kicker mb-1">Tone</dt>
                <dd
                  className="font-display text-2xl italic text-foreground"
                  style={{
                    fontVariationSettings:
                      '"opsz" 96, "SOFT" 60, "WONK" 1',
                  }}
                >
                  {kit.voice.tone}
                </dd>
              </div>
              {kit.voice.example_phrases &&
                kit.voice.example_phrases.length > 0 && (
                  <div>
                    <dt className="kicker mb-2">Example phrases</dt>
                    <dd>
                      <ul className="space-y-1.5 font-display text-lg italic leading-snug text-foreground/80">
                        {kit.voice.example_phrases.map((p, i) => (
                          <li key={i} className="before:mr-3 before:text-amber before:content-['—']">
                            {p}
                          </li>
                        ))}
                      </ul>
                    </dd>
                  </div>
                )}
              {kit.voice.banned_words &&
                kit.voice.banned_words.length > 0 && (
                  <div>
                    <dt className="kicker mb-2">Banned</dt>
                    <dd className="font-mono text-sm text-foreground/75">
                      {kit.voice.banned_words.join(" · ")}
                    </dd>
                  </div>
                )}
            </dl>
          </Section>
        )}
      </div>

      <footer className="mt-10 flex flex-wrap gap-6 border-t border-border pt-8">
        <div className="kicker w-full">Use this kit in →</div>
        <Link
          to={`/flyers/new?brand_kit=${encodeURIComponent(slug)}`}
          className="font-display text-lg italic text-foreground underline decoration-amber decoration-2 underline-offset-[6px] hover:text-amber"
          style={{
            fontVariationSettings: '"opsz" 48, "SOFT" 60, "WONK" 1',
          }}
        >
          a flyer
        </Link>
        <Link
          to={`/brochures/new?brand_kit=${encodeURIComponent(slug)}`}
          className="font-display text-lg italic text-foreground underline decoration-amber decoration-2 underline-offset-[6px] hover:text-amber"
          style={{
            fontVariationSettings: '"opsz" 48, "SOFT" 60, "WONK" 1',
          }}
        >
          a brochure
        </Link>
        <Link
          to={`/social/posts/new?brand_kit=${encodeURIComponent(slug)}`}
          className="font-display text-lg italic text-foreground underline decoration-amber decoration-2 underline-offset-[6px] hover:text-amber"
          style={{
            fontVariationSettings: '"opsz" 48, "SOFT" 60, "WONK" 1',
          }}
        >
          a post
        </Link>
        <Link
          to={`/social/campaigns/new?brand_kit=${encodeURIComponent(slug)}`}
          className="font-display text-lg italic text-foreground underline decoration-amber decoration-2 underline-offset-[6px] hover:text-amber"
          style={{
            fontVariationSettings: '"opsz" 48, "SOFT" 60, "WONK" 1',
          }}
        >
          a campaign
        </Link>
      </footer>
    </div>
  );
}
