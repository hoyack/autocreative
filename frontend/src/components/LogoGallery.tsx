import type { components } from "@/api/schema.gen";

type BrandLogo = components["schemas"]["BrandLogo"];

interface LogoGalleryProps {
  slug: string;
  logos: BrandLogo[];
}

/**
 * Grid of logo previews. Each logo is fetched as binary via the new
 * GET /api/v1/brand-kits/{slug}/logos/{filename} route (added in this plan's
 * Task 1).
 *
 * BrandLogo.path is relative to the kit dir — e.g. "logos/primary.png". The
 * new route mounts under .brand-kits/<slug>/logos/<filename>, so we strip the
 * leading "logos/" prefix from BrandLogo.path before constructing the URL.
 *
 * Security posture: all scraped strings (variant / format / aspect_ratio)
 * render as JSX text children, escaped by React. No raw-HTML injection points
 * (T-2 mitigation).
 */
export function LogoGallery({ slug, logos }: LogoGalleryProps) {
  if (!logos || logos.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">No logos available.</p>
    );
  }
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
      {logos.map((logo) => {
        // BrandLogo.path is "logos/primary.png" — strip the prefix.
        const filename = logo.path.replace(/^logos[/\\]/, "");
        const url = `/api/v1/brand-kits/${slug}/logos/${encodeURIComponent(filename)}`;
        return (
          <div
            key={logo.path}
            className="flex flex-col items-center gap-1 rounded border p-3"
          >
            <img
              src={url}
              alt={`${logo.variant} ${logo.format}`}
              className="max-h-32 max-w-full object-contain"
              loading="lazy"
            />
            <span className="text-xs font-medium">{logo.variant}</span>
            <span className="text-muted-foreground text-[10px]">
              {logo.format} | aspect {logo.aspect_ratio.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
