// Plan 21-06 Task 1 (TDD).
//
// Two tests for the flyer creation form:
//   1. rejects empty title — zod min(1) error surfaces inline
//   2. on valid submit, POSTs to /api/v1/flyers with the chosen preset
//      duplicated into BOTH event.style_preset (nested) AND top-level preset
//      (per 21-RESEARCH.md "Reuse note" line 334).
//
// The default msw-server handler for POST /api/v1/flyers is defined in
// src/test/msw-server.ts; this test overrides it via server.use(...) so the
// submitted body can be captured for assertions.
import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { server } from "@/test/msw-server";
import { renderWithProviders } from "@/test/test-utils";

import { NewFlyerPage } from "./new";

describe("NewFlyerPage", () => {
  it("rejects empty title", async () => {
    renderWithProviders(<NewFlyerPage />);
    await userEvent.click(
      screen.getByRole("button", { name: /generate/i }),
    );
    // zod v4 min(1) message can be "Too small" / "at least 1" / "required".
    // Use a broad regex so version drift doesn't break this test.
    await waitFor(() => {
      expect(
        screen.getByText(
          /at least 1|too small|required|must contain|invalid/i,
        ),
      ).toBeInTheDocument();
    });
  });

  it("submits with preset duplicated into event.style_preset", async () => {
    let captured: {
      event?: Record<string, unknown>;
      preset?: string;
    } | null = null;
    server.use(
      http.post("/api/v1/flyers", async ({ request }) => {
        captured = (await request.json()) as {
          event: Record<string, unknown>;
          preset: string;
        };
        return HttpResponse.json(
          { job_id: "01J9ABCDEFGHJKMNPQRSTVWXYZ" },
          { status: 202 },
        );
      }),
    );

    renderWithProviders(<NewFlyerPage />);
    await userEvent.type(
      screen.getByLabelText(/^title$/i),
      "Friday Show",
    );
    await userEvent.type(screen.getByLabelText(/^date$/i), "2026-05-01");
    await userEvent.type(screen.getByLabelText(/^time$/i), "7:00 PM");
    await userEvent.type(
      screen.getByLabelText(/venue name/i),
      "The Hall",
    );
    await userEvent.type(
      screen.getByLabelText(/venue address/i),
      "1 Main St",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /generate/i }),
    );

    // Wait for the onSuccess toast to render (signals the POST resolved).
    await screen.findByText(/flyer enqueued/i);
    expect(captured).not.toBeNull();
    // The default preset "photorealistic" is duplicated into both fields.
    expect(captured!.preset).toBe("photorealistic");
    expect(captured!.event!.style_preset).toBe("photorealistic");
  });
});
