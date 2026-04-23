// Plan 21-08 Task 1 (TDD).
//
// Two tests for the social post creation form:
//   1. rejects empty brand_kit_slug — zod min(1) error surfaces inline
//      when the user submits with only a topic typed.
//   2. on valid submit, POSTs to /api/v1/social/posts with the chosen
//      platform + intent (defaults: linkedin / announcement).
//
// No default msw-server handler exists for POST /api/v1/social/posts; the
// valid-submit test installs one via server.use(...) so the body can be
// captured for assertions. Per src/test/setup.ts::onUnhandledRequest ===
// "error", an unhandled POST in the invalid-slug test would fail loudly —
// but zod validation blocks that submit client-side so no POST is issued.
import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { server } from "@/test/msw-server";
import { renderWithProviders } from "@/test/test-utils";

import { NewSocialPostPage } from "./new";

describe("NewSocialPostPage", () => {
  it("rejects empty brand_kit_slug", async () => {
    renderWithProviders(<NewSocialPostPage />);
    // brand_kit_slug starts empty (no query param). Type a topic so that
    // field is valid, then submit — the slug error should surface.
    await userEvent.type(
      screen.getByLabelText(/topic/i),
      "Launch announcement",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /generate post/i }),
    );
    // zod v4 min(1) message is "Too small: expected string to have >=1
    // characters". Broad regex tolerates zod version drift (v3 / v4).
    const matches = await screen.findAllByText(
      /at least 1|too small|required|must contain|invalid/i,
    );
    expect(matches.length).toBeGreaterThan(0);
  });

  it("submits to /social/posts with the chosen platform + intent", async () => {
    let captured: {
      brand_kit_slug?: string;
      platform?: string;
      intent?: string;
      topic?: string;
      cta?: string | null;
      image_hint?: string | null;
      style_preset?: string | null;
    } | null = null;
    server.use(
      http.post("/api/v1/social/posts", async ({ request }) => {
        captured = (await request.json()) as typeof captured;
        return HttpResponse.json(
          { job_id: "01J9ABCDEFGHJKMNPQRSTVWXYZ" },
          { status: 202 },
        );
      }),
    );

    renderWithProviders(<NewSocialPostPage />);
    await userEvent.type(
      screen.getByLabelText(/brand kit slug/i),
      "shrubnet",
    );
    await userEvent.type(
      screen.getByLabelText(/topic/i),
      "Q2 product launch",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /generate post/i }),
    );

    // Wait for the onSuccess toast to render (signals POST resolved).
    await screen.findByText(/post enqueued/i);
    expect(captured).not.toBeNull();
    expect(captured!.brand_kit_slug).toBe("shrubnet");
    expect(captured!.topic).toBe("Q2 product launch");
    expect(captured!.platform).toBe("linkedin"); // default
    expect(captured!.intent).toBe("announcement"); // default
  });
});
