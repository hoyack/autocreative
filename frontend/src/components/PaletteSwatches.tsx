import type { components } from "@/api/schema.gen";

// Pull the palette type out of BrandKitDetail.brand_kit.palette. `palette` is
// nullable on the BrandKit model, so we use NonNullable<...> to narrow to the
// populated shape — this component is only mounted when the caller has
// verified kit.palette is present.
type BrandPalette = NonNullable<
  components["schemas"]["BrandKitDetail"]["brand_kit"]["palette"]
>;

interface PaletteSwatchesProps {
  palette: BrandPalette;
}

const ROLE_ORDER = [
  "primary",
  "secondary",
  "accent",
  "neutral_dark",
  "neutral_light",
] as const;

/**
 * Render a brand palette as a row of colored swatches.
 *
 * Per 21-CONTEXT.md <specifics>: "palette swatches (CSS divs with hex
 * backgrounds)". Inline style is intentional — Tailwind cannot generate
 * arbitrary hex utilities at runtime. React's inline-style object is an
 * XSS-safe rendering path (values are treated as property values, not
 * interpreted HTML), which closes T-2 for this component.
 */
export function PaletteSwatches({ palette }: PaletteSwatchesProps) {
  return (
    <div className="flex flex-wrap gap-3">
      {ROLE_ORDER.map((role) => {
        // Cast via `unknown` first — the generated BrandPalette type exposes
        // both named-role fields and an `extras` index map, and TS's overlap
        // check rejects a direct Record cast. The runtime shape is exactly
        // { [role]: ColorUsage }, so the narrow ColorUsage lookup is safe.
        const usage = (
          palette as unknown as Record<
            string,
            { hex: string; usage_hint?: string | null } | undefined
          >
        )[role];
        if (!usage) return null;
        return (
          <div key={role} className="flex flex-col items-start gap-1">
            <div
              className="h-16 w-16 rounded border"
              style={{ backgroundColor: usage.hex }}
              aria-label={`${role} ${usage.hex}`}
            />
            <span className="text-xs font-medium">{role.replace("_", " ")}</span>
            <span className="text-muted-foreground font-mono text-[10px]">
              {usage.hex}
            </span>
            {usage.usage_hint && (
              <span className="text-muted-foreground text-[10px]">
                {usage.usage_hint}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
