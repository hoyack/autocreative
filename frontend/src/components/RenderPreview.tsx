// Render a single artifact URL as either an inline <img> (PNG/JPG) or a
// download <a> (PDF). Per 21-CONTEXT.md <specifics> "Render preview
// pattern" — skip inline PDF rendering for v1 because the embed-tag UX is
// poor across browsers. This file intentionally renders NO embed tags.
//
// WR-04: PDF detection is done via a STRICT `.pdf` suffix regex OR an
// explicit `isPdf` prop. The old permissive substring check on the URL
// path (matching any occurrence of /pdf) is gone — it false-positives on
// any URL whose path contains the letters "pdf" as a substring (e.g. a
// render id starting with "pdf").

interface RenderPreviewProps {
  url: string;
  alt?: string;
  className?: string;
  /** Explicit content-type hint. When true, force the PDF-download
   *  branch regardless of URL suffix. Callers with known content type
   *  (e.g. brochures/status.tsx's pdf_render_url slot) should set this.
   *  Omitting the prop falls back to a strict `.pdf` suffix match. */
  isPdf?: boolean;
}

/** Suggest a sensible download filename for a render URL.
 *  For `/api/v1/renders/{ulid}/image` returns `{ulid}.pdf` (IN-01 companion).
 *  Otherwise falls back to the last non-empty path segment with a `.pdf`
 *  extension appended if missing. */
function suggestPdfFilename(url: string): string {
  // Strip query/fragment before inspecting path.
  const pathOnly = url.split("?")[0].split("#")[0];
  const segments = pathOnly.split("/").filter(Boolean);
  // /api/v1/renders/{ulid}/image  -> last two segments are [ulid, "image"]
  if (segments.length >= 2 && segments[segments.length - 1] === "image") {
    return `${segments[segments.length - 2]}.pdf`;
  }
  // Generic: last segment. If it doesn't already end with .pdf, append.
  const last = segments[segments.length - 1] ?? "render";
  return /\.pdf$/i.test(last) ? last : `${last}.pdf`;
}

// Strict suffix check. Matches exactly `.pdf` at end of URL OR
// immediately before a query string. No substring matching.
const PDF_SUFFIX_RE = /\.pdf($|\?)/i;

export function RenderPreview({
  url,
  alt = "render",
  className,
  isPdf,
}: RenderPreviewProps) {
  const looksLikePdf = isPdf === true || PDF_SUFFIX_RE.test(url);
  if (looksLikePdf) {
    const filename = suggestPdfFilename(url);
    return (
      <a
        href={url}
        download={filename}
        className={`inline-flex items-center gap-2 rounded border px-3 py-2 text-sm hover:bg-muted ${className ?? ""}`}
      >
        Download PDF
      </a>
    );
  }
  return (
    <img
      src={url}
      alt={alt}
      className={`max-w-full rounded border ${className ?? ""}`}
      loading="lazy"
    />
  );
}
