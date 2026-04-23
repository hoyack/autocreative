// Plan 21-05 Task 3 (TDD).
//
// Two tests for the brand-kit list page:
//   1. empty state copy when the backend reports total=0
//   2. one card rendered per summary when the backend returns items
//
// Both tests install a per-test msw handler for GET /api/v1/brand-kits; the
// default msw-server does not register this path.
import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";

import { server } from "@/test/msw-server";
import { renderWithProviders } from "@/test/test-utils";

import { BrandKitsListPage } from "./list";

describe("BrandKitsListPage", () => {
  it("renders the empty state when total is 0", async () => {
    server.use(
      http.get("/api/v1/brand-kits", () =>
        HttpResponse.json({ items: [], total: 0, limit: 24, offset: 0 }),
      ),
    );
    renderWithProviders(<BrandKitsListPage />);
    expect(
      await screen.findByText(/no brand kits yet/i),
    ).toBeInTheDocument();
  });

  it("renders cards for each summary in the response", async () => {
    server.use(
      http.get("/api/v1/brand-kits", () =>
        HttpResponse.json({
          items: [
            {
              slug: "shrubnet",
              name: "Shrubnet",
              source_url: "https://shrubnet.com",
              scraped_at: "2026-04-01T00:00:00Z",
            },
            {
              slug: "hoyack",
              name: "Hoyack",
              source_url: "https://hoyack.com",
              scraped_at: "2026-04-02T00:00:00Z",
            },
          ],
          total: 2,
          limit: 24,
          offset: 0,
        }),
      ),
    );
    renderWithProviders(<BrandKitsListPage />);
    expect(await screen.findByText("Shrubnet")).toBeInTheDocument();
    expect(screen.getByText("Hoyack")).toBeInTheDocument();
  });
});
