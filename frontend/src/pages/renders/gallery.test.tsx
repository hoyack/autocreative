// Plan 21-11 Task 2 (TDD).
//
// Two tests for the renders gallery page:
//   1. empty-state text when total=0
//   2. PNG kinds render via <RenderPreview/> inline <img>; PDF kinds
//      render a download <a> link — both using /api/v1/renders/{id}/image
//      as the preview URL (built client-side from the summary row).
//
// Uses the project-standard renderWithProviders helper (QueryClient +
// MemoryRouter + Toaster) and the msw server from src/test/msw-server.ts.
import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";

import { server } from "@/test/msw-server";
import { renderWithProviders } from "@/test/test-utils";

import { RenderGalleryPage } from "./gallery";

describe("RenderGalleryPage", () => {
  it("renders empty state when total is 0", async () => {
    server.use(
      http.get("/api/v1/renders", () =>
        HttpResponse.json({ items: [], total: 0, limit: 24, offset: 0 }),
      ),
    );
    renderWithProviders(<RenderGalleryPage />);
    expect(await screen.findByText(/no renders\./i)).toBeInTheDocument();
  });

  it("renders <img> for PNG kinds and download link for PDF kinds", async () => {
    // 26-char ULIDs for both rows — matches the path-param ULID invariant.
    const pngId = "01PNG" + "A".repeat(21);
    const pdfId = "01PDF" + "A".repeat(21);
    server.use(
      http.get("/api/v1/renders", () =>
        HttpResponse.json({
          items: [
            {
              id: pngId,
              kind: "flyer_final",
              comfy_job_id: null,
              created_at: new Date().toISOString(),
            },
            {
              id: pdfId,
              kind: "brochure_pdf",
              comfy_job_id: null,
              created_at: new Date().toISOString(),
            },
          ],
          total: 2,
          limit: 24,
          offset: 0,
        }),
      ),
    );
    renderWithProviders(<RenderGalleryPage />);

    // PNG card -> <img> with /api/v1/renders/.../image src.
    const img = await screen.findByRole("img", { name: /flyer_final/i });
    expect(img).toHaveAttribute("src", `/api/v1/renders/${pngId}/image`);

    // PDF card -> Download link pointing at the same streaming route.
    const dl = screen.getByText(/download pdf/i);
    expect(dl.closest("a")).toHaveAttribute(
      "href",
      `/api/v1/renders/${pdfId}/image`,
    );
  });
});
