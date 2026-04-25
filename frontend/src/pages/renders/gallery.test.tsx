// Plan 21-11 Task 2 (TDD) + Plan 22-06 Task 3 (TDD KINDS update).
//
// Tests for the renders gallery page:
//   1. empty-state text when total=0
//   2. PNG kinds render via <RenderPreview/> inline <img>; PDF kinds
//      render a download <a> link — both using /api/v1/renders/{id}/image
//      as the preview URL (built client-side from the summary row).
//   3. (Phase 22) KINDS filter dropdown includes flyer_event_final +
//      flyer_info_final and does NOT include the deprecated flyer_final.
//
// Uses the project-standard renderWithProviders helper (QueryClient +
// MemoryRouter + Toaster) and the msw server from src/test/msw-server.ts.
import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { screen, within } from "@testing-library/react";

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
    expect(await screen.findByText(/archive is empty\./i)).toBeInTheDocument();
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
              kind: "flyer_event_final",
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
    const img = await screen.findByRole("img", { name: /flyer_event_final/i });
    expect(img).toHaveAttribute("src", `/api/v1/renders/${pngId}/image`);

    // PDF card -> Download link pointing at the same streaming route.
    // The editorial restyle shows a big "PDF" glyph + "Click to download →"
    // caption in the card; both live inside the same <a download> element.
    const dl = screen.getByText(/click to download/i);
    expect(dl.closest("a")).toHaveAttribute(
      "href",
      `/api/v1/renders/${pdfId}/image`,
    );
  });
});

describe("RenderGalleryPage — Phase 22 KINDS", () => {
  it("includes both flyer_event_final and flyer_info_final in the kind filter", async () => {
    // Default empty-state response keeps the test focused on filter UI.
    server.use(
      http.get("/api/v1/renders", () =>
        HttpResponse.json({ items: [], total: 0, limit: 24, offset: 0 }),
      ),
    );
    renderWithProviders(<RenderGalleryPage />);
    // The page renders one Select (Kind). It's the only combobox on the
    // page, so finding it by role is unambiguous.
    const trigger = await screen.findByRole("combobox");
    await userEvent.click(trigger);
    const listbox = await screen.findByRole("listbox");
    expect(within(listbox).getByText("flyer_event_final")).toBeInTheDocument();
    expect(within(listbox).getByText("flyer_info_final")).toBeInTheDocument();
  });

  it("does NOT include the deprecated flyer_final kind", async () => {
    server.use(
      http.get("/api/v1/renders", () =>
        HttpResponse.json({ items: [], total: 0, limit: 24, offset: 0 }),
      ),
    );
    renderWithProviders(<RenderGalleryPage />);
    const trigger = await screen.findByRole("combobox");
    await userEvent.click(trigger);
    const listbox = await screen.findByRole("listbox");
    // queryByText must be exact "flyer_final" — flyer_event_final and
    // flyer_info_final both START with "flyer_" but not match "flyer_final"
    // exactly when pinned via the string overload.
    expect(within(listbox).queryByText("flyer_final")).not.toBeInTheDocument();
  });
});
