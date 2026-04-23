// Plan 21-09 Task 1 (TDD).
//
// Two tests for the social campaign creation form:
//   1. rejects submission with no platforms selected — the zod
//      `platforms: z.array(...).min(1)` error surfaces inline when the
//      user submits with brand_kit_slug + topic typed but zero checkboxes
//      ticked.
//   2. on valid submit (2 platforms checked), POSTs to
//      /api/v1/social/campaigns with the selected platforms array
//      serialized correctly (["linkedin", "twitter"] in this test).
//
// No default msw-server handler exists for POST /api/v1/social/campaigns;
// the valid-submit test installs one via server.use(...) so the body can
// be captured for assertions. Per src/test/setup.ts::onUnhandledRequest ===
// "error" an unhandled POST in the invalid-platforms test would fail
// loudly — but zod validation blocks that submit client-side so no POST
// is issued.
//
// Checkbox interaction note: the 21-09 form wraps each Checkbox in a
// <label> that also contains the platform text. userEvent.click on the
// label text delegates to the checkbox per the HTML label contract, so
// the two valid-submit clicks select "linkedin" + "twitter" via the
// label text.
import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { server } from "@/test/msw-server";
import { renderWithProviders } from "@/test/test-utils";

import { NewCampaignPage } from "./new";

describe("NewCampaignPage", () => {
  it("rejects submission with no platforms selected", async () => {
    renderWithProviders(<NewCampaignPage />);
    await userEvent.type(
      screen.getByLabelText(/brand kit slug/i),
      "shrubnet",
    );
    await userEvent.type(screen.getByLabelText(/topic/i), "Q2 launch");
    await userEvent.click(
      screen.getByRole("button", { name: /generate campaign/i }),
    );
    // The zod schema says
    //   platforms: z.array(z.enum(PLATFORMS)).min(1, "select at least one platform").max(10)
    // so the FormMessage should surface "select at least one platform".
    expect(
      await screen.findByText(/select at least one platform/i),
    ).toBeInTheDocument();
  });

  it("submits the selected platforms array on valid input", async () => {
    let captured: {
      brand_kit_slug?: string;
      platforms?: string[];
      intent?: string;
      topic?: string;
      cta?: string | null;
      style_preset?: string | null;
    } | null = null;
    server.use(
      http.post("/api/v1/social/campaigns", async ({ request }) => {
        captured = (await request.json()) as typeof captured;
        return HttpResponse.json(
          { job_id: "01J9ABCDEFGHJKMNPQRSTVWXYZ" },
          { status: 202 },
        );
      }),
    );

    renderWithProviders(<NewCampaignPage />);
    await userEvent.type(
      screen.getByLabelText(/brand kit slug/i),
      "shrubnet",
    );
    await userEvent.type(screen.getByLabelText(/topic/i), "Q2 launch");
    // Click two platform labels — the HTML <label> wrapper delegates the
    // click to the wrapped Checkbox so this toggles state.
    await userEvent.click(screen.getByText("linkedin"));
    await userEvent.click(screen.getByText("twitter"));
    await userEvent.click(
      screen.getByRole("button", { name: /generate campaign/i }),
    );

    // Wait for the onSuccess toast (signals POST resolved).
    await screen.findByText(/campaign enqueued/i);
    expect(captured).not.toBeNull();
    expect(captured!.brand_kit_slug).toBe("shrubnet");
    expect(captured!.topic).toBe("Q2 launch");
    expect(captured!.platforms).toEqual(["linkedin", "twitter"]);
    expect(captured!.intent).toBe("announcement"); // default
  });
});
