// Render a single artifact URL as either an inline <img> (PNG/JPG) or a
// download <a> (PDF). Per 21-CONTEXT.md <specifics> "Render preview
// pattern" — skip inline PDF rendering for v1 because <object> UX is
// poor across browsers. NEVER use <object> here.

interface RenderPreviewProps {
  url: string;
  alt?: string;
  className?: string;
}

export function RenderPreview({
  url,
  alt = "render",
  className,
}: RenderPreviewProps) {
  const lower = url.toLowerCase();
  // Treat any URL ending in .pdf, .pdf?..., or containing /pdf as a PDF.
  if (
    lower.endsWith(".pdf") ||
    lower.includes(".pdf?") ||
    lower.includes("/pdf")
  ) {
    const filename =
      url.split("/").filter(Boolean).slice(-2, -1)[0] ?? "render.pdf";
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
