// Plan 21-10 Task 2 (TDD).
//
// Two tests for the jobs list page:
//   1. empty-state row when the backend reports total=0
//   2. each row links to the kind-specific status page (flyer -> /flyers/:id,
//      brochure -> /brochures/:id)
//
// The default msw-server registers /api/v1/jobs/:id (returns succeeded) —
// that covers the per-row <JobStatusBadge> subscription for non-terminal
// rows in this test fixture.
import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";

import { server } from "@/test/msw-server";
import { renderWithProviders } from "@/test/test-utils";

import { JobsListPage } from "./list";

describe("JobsListPage", () => {
  it("renders an empty-state row when total is 0", async () => {
    server.use(
      http.get("/api/v1/jobs", () =>
        HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 }),
      ),
    );
    renderWithProviders(<JobsListPage />);
    expect(await screen.findByText(/no jobs\./i)).toBeInTheDocument();
  });

  it("links each row to the kind-specific status page", async () => {
    const flyerId = "01FLYER" + "A".repeat(19); // 26 chars
    const brocId = "01BROC" + "A".repeat(20); // 26 chars
    server.use(
      http.get("/api/v1/jobs", () =>
        HttpResponse.json({
          items: [
            {
              id: flyerId,
              kind: "flyer",
              status: "succeeded",
              started_at: new Date().toISOString(),
              completed_at: new Date().toISOString(),
              error_detail: null,
              result_ref: "/api/v1/renders/01XX/image",
              created_at: new Date().toISOString(),
            },
            {
              id: brocId,
              kind: "brochure",
              status: "running",
              started_at: new Date().toISOString(),
              completed_at: null,
              error_detail: null,
              result_ref: null,
              created_at: new Date().toISOString(),
            },
          ],
          total: 2,
          limit: 50,
          offset: 0,
        }),
      ),
    );
    renderWithProviders(<JobsListPage />);

    // Rows are rendered as "<first-12>..." text inside a <Link>.
    const flyerLink = await screen.findByText(`${flyerId.slice(0, 12)}...`);
    expect(flyerLink.closest("a")).toHaveAttribute("href", `/flyers/${flyerId}`);

    const brocLink = screen.getByText(`${brocId.slice(0, 12)}...`);
    expect(brocLink.closest("a")).toHaveAttribute(
      "href",
      `/brochures/${brocId}`,
    );
  });
});
