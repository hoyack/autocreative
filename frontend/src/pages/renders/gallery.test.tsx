// Plan 21-11 Task 2 (TDD) + Plan 22-06 Task 3 (TDD KINDS update) +
// Plan 24.2-02 Task 2 (TDD render-delete flow).
//
// Tests for the renders gallery page:
//   1. empty-state text when total=0
//   2. PNG kinds render via <RenderPreview/> inline <img>; PDF kinds
//      render a download <a> link — both using /api/v1/renders/{id}/image
//      as the preview URL (built client-side from the summary row).
//   3. (Phase 22) KINDS filter dropdown includes flyer_event_final +
//      flyer_info_final and does NOT include the deprecated flyer_final.
//   4. (Plan 24.2-02) Trash button + AlertDialog + DELETE mutation flow:
//      - Trash2 button on every card
//      - Click opens AlertDialog with destructive confirm
//      - Confirm fires DELETE + optimistic remove + success toast
//      - Error response restores card + error toast
//
// Uses the project-standard renderWithProviders helper (QueryClient +
// MemoryRouter + Toaster) and the msw server from src/test/msw-server.ts.
import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { screen, waitFor, within } from "@testing-library/react";

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

describe("RenderGalleryPage — delete flow (Plan 24.2-02)", () => {
  // Helper: build N PNG render summary rows with predictable ULIDs.
  function pngRows(n: number) {
    return Array.from({ length: n }, (_, i) => ({
      id: `01PNG${String(i).padStart(2, "0")}` + "A".repeat(19),
      kind: "flyer_event_final",
      comfy_job_id: null,
      created_at: new Date().toISOString(),
    }));
  }

  it("renders a Trash2 button on every render card", async () => {
    const items = pngRows(2);
    server.use(
      http.get("/api/v1/renders", () =>
        HttpResponse.json({
          items,
          total: items.length,
          limit: 24,
          offset: 0,
        }),
      ),
    );
    renderWithProviders(<RenderGalleryPage />);
    // Wait for cards, then assert one delete button per card.
    await screen.findAllByRole("img", { name: /flyer_event_final/i });
    const deleteButtons = screen.getAllByRole("button", {
      name: /delete render/i,
    });
    expect(deleteButtons).toHaveLength(items.length);
  });

  it("clicking trash opens an AlertDialog with destructive confirm and a cancel button", async () => {
    const items = pngRows(1);
    server.use(
      http.get("/api/v1/renders", () =>
        HttpResponse.json({
          items,
          total: items.length,
          limit: 24,
          offset: 0,
        }),
      ),
    );
    renderWithProviders(<RenderGalleryPage />);

    const trashButton = await screen.findByRole("button", {
      name: /delete render/i,
    });
    await userEvent.click(trashButton);

    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText(/delete render\?/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/cannot be undone/i)).toBeInTheDocument();
    // Cancel button (default focus per Radix convention).
    expect(
      within(dialog).getByRole("button", { name: /cancel/i }),
    ).toBeInTheDocument();
    // Destructive confirm button — name matches /delete/ (not /cancel/).
    const confirm = within(dialog).getByRole("button", {
      name: /^delete$/i,
    });
    expect(confirm).toBeInTheDocument();
  });

  it("confirming the dialog fires DELETE, removes the card optimistically, and shows a success toast", async () => {
    const items = pngRows(1);
    const targetId = items[0].id;
    let deleteHits = 0;
    // Stateful list — the GET handler reflects the current set so the
    // post-delete invalidate-and-refetch sees the row really removed
    // (otherwise the optimistic-removed card would reappear on refetch).
    let currentItems = [...items];
    server.use(
      http.get("/api/v1/renders", () =>
        HttpResponse.json({
          items: currentItems,
          total: currentItems.length,
          limit: 24,
          offset: 0,
        }),
      ),
      http.delete("/api/v1/renders/:render_id", ({ params }) => {
        deleteHits += 1;
        expect(params.render_id).toBe(targetId);
        currentItems = currentItems.filter((r) => r.id !== params.render_id);
        return new HttpResponse(null, { status: 204 });
      }),
    );

    renderWithProviders(<RenderGalleryPage />);

    // Wait for the card, then click trash + confirm.
    await screen.findByRole("img", { name: /flyer_event_final/i });
    await userEvent.click(
      screen.getByRole("button", { name: /delete render/i }),
    );

    const dialog = await screen.findByRole("alertdialog");
    await userEvent.click(within(dialog).getByRole("button", { name: /^delete$/i }));

    // Card disappears (optimistic update + invalidate).
    await waitFor(() => {
      expect(
        screen.queryByRole("img", { name: /flyer_event_final/i }),
      ).not.toBeInTheDocument();
    });
    // DELETE was made exactly once with the right id.
    expect(deleteHits).toBe(1);
    // Success toast surfaces in the Toaster mounted by renderWithProviders.
    expect(
      await screen.findByText(/render deleted/i),
    ).toBeInTheDocument();
  });

  it("error response restores the card and surfaces an error toast", async () => {
    const items = pngRows(1);
    server.use(
      http.get("/api/v1/renders", () =>
        HttpResponse.json({
          items,
          total: items.length,
          limit: 24,
          offset: 0,
        }),
      ),
      http.delete("/api/v1/renders/:render_id", () =>
        HttpResponse.json(
          { detail: "boom", error_type: "Internal", trace_id: "" },
          { status: 500 },
        ),
      ),
    );

    renderWithProviders(<RenderGalleryPage />);

    await screen.findByRole("img", { name: /flyer_event_final/i });
    await userEvent.click(
      screen.getByRole("button", { name: /delete render/i }),
    );

    const dialog = await screen.findByRole("alertdialog");
    await userEvent.click(within(dialog).getByRole("button", { name: /^delete$/i }));

    // Card restored after error path resolves.
    await waitFor(() => {
      expect(
        screen.getByRole("img", { name: /flyer_event_final/i }),
      ).toBeInTheDocument();
    });
    // Error toast surfaces in the Toaster.
    expect(await screen.findByText(/boom/i)).toBeInTheDocument();
  });
});
