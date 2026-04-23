// WR-04 regression: RenderPreview must not treat arbitrary URL path
// substrings as PDFs. The previous implementation used
// `lower.includes("/pdf")` which false-positives on any ULID whose
// lowercased form starts with "pdf" (unlikely on 01H* epoch but latent).
//
// Also covers the explicit isPdf prop which callers with content-type
// knowledge (brochures/status.tsx's pdf_render_url slot) use to force
// the download branch deterministically.
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { RenderPreview } from "./RenderPreview";

describe("RenderPreview", () => {
  it("does not treat a URL containing the substring '/pdf' as a PDF (WR-04)", () => {
    // A render id starting with 'pdf' in the path — the exact WR-04 case.
    // The URL has NO .pdf extension; the image branch MUST win.
    const url = "/api/v1/renders/pdf01habcdefghjkmnpqrstvwxyz/image";
    renderWithProviders(<RenderPreview url={url} alt="flyer render" />);
    const img = screen.getByRole("img", { name: /flyer render/i });
    expect(img).toHaveAttribute("src", url);
    // And there is NO anchor with a `download` attribute.
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("renders a download anchor for a URL ending in .pdf", () => {
    const url = "/files/report.pdf";
    renderWithProviders(<RenderPreview url={url} />);
    const anchor = screen.getByRole("link", { name: /download pdf/i });
    expect(anchor).toHaveAttribute("href", url);
    expect(anchor).toHaveAttribute("download");
  });

  it("renders a download anchor for a URL ending in .pdf?query", () => {
    const url = "/files/report.pdf?v=2";
    renderWithProviders(<RenderPreview url={url} />);
    const anchor = screen.getByRole("link", { name: /download pdf/i });
    expect(anchor).toHaveAttribute("href", url);
  });

  it("renders a download anchor when isPdf=true even without a .pdf suffix", () => {
    // Caller (e.g. brochures/status.tsx pdf_render_url slot) asserts
    // content type via the isPdf prop. The anchor must render even
    // though the URL has no .pdf extension.
    const url = "/api/v1/renders/01HBROCHUREPDF000000000000/image";
    renderWithProviders(<RenderPreview url={url} isPdf />);
    const anchor = screen.getByRole("link", { name: /download pdf/i });
    expect(anchor).toHaveAttribute("href", url);
    // IN-01 companion: suggested filename must end with .pdf so the OS
    // Save dialog picks up the extension. Either {ulid}.pdf or any
    // non-empty string ending in ".pdf" is acceptable.
    const downloadAttr = anchor.getAttribute("download");
    expect(downloadAttr).toMatch(/\.pdf$/);
  });
});
