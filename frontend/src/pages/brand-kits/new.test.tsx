// Plan 21-05 Task 3 (TDD).
//
// Two tests for the brand-kit scrape form:
//   1. invalid URL surfaces a zod validation error (client-side)
//   2. valid input POSTs to /api/v1/brand-kits/fetch and surfaces the success
//      toast
//
// Both render the page through renderWithProviders (QueryClient + MemoryRouter)
// and use msw to intercept the POST. The default msw-server handlers do NOT
// cover /brand-kits/fetch, so each test that needs it installs a per-test
// handler via server.use(...).
import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { server } from "@/test/msw-server";
import { renderWithProviders } from "@/test/test-utils";

import { ScrapeBrandKitPage } from "./new";

describe("ScrapeBrandKitPage", () => {
  it("rejects an invalid URL", async () => {
    renderWithProviders(<ScrapeBrandKitPage />);
    await userEvent.type(screen.getByLabelText(/source url/i), "not-a-url");
    await userEvent.type(screen.getByLabelText(/slug/i), "demo");
    await userEvent.click(screen.getByRole("button", { name: /scrape/i }));

    // zod's .url() message is "Invalid url" / "Invalid URL" depending on
    // version; match both. Use waitFor so RHF has time to flush the state
    // update after the async resolver rejects.
    await waitFor(() => {
      expect(screen.getByText(/invalid url/i)).toBeInTheDocument();
    });
  });

  it("submits + posts to /brand-kits/fetch on valid input", async () => {
    let called = false;
    let capturedBody: { url?: string; slug?: string } = {};
    server.use(
      http.post("/api/v1/brand-kits/fetch", async ({ request }) => {
        called = true;
        capturedBody = (await request.json()) as {
          url: string;
          slug: string;
        };
        return HttpResponse.json(
          { job_id: "01J9ABCDEFGHJKMNPQRSTVWXYZ" },
          { status: 202 },
        );
      }),
    );

    renderWithProviders(<ScrapeBrandKitPage />);
    await userEvent.type(
      screen.getByLabelText(/source url/i),
      "https://example.com",
    );
    await userEvent.type(screen.getByLabelText(/slug/i), "demo-co");
    await userEvent.click(screen.getByRole("button", { name: /scrape/i }));

    // Wait for the mutation onSuccess to fire (toast appears in the DOM).
    await screen.findByText(/scrape enqueued/i);
    expect(called).toBe(true);
    expect(capturedBody.slug).toBe("demo-co");
    expect(capturedBody.url).toBe("https://example.com");
  });
});
