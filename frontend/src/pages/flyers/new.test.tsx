// Plan 22-06 Task 2 (TDD) — extends Plan 21-06 with template + subtype coverage.
//
// The form now has:
//   * a `template` <Select> with 6 options (mirrors flyer_generator/flyer/schemas/)
//   * an `event.subtype` <Select> with 2 options ("event" + "info")
//   * conditional event-only fields (date/time/venue/fees) — visible only when
//     subtype === "event"
//   * conditional info-only fields (description + call_to_action) — visible only
//     when subtype === "info"
//
// The default msw-server handler for POST /api/v1/flyers is defined in
// src/test/msw-server.ts; tests that need to capture the submitted body
// override via `server.use(...)`.
import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { server } from "@/test/msw-server";
import { renderWithProviders } from "@/test/test-utils";

import { NewFlyerPage } from "./new";

describe("NewFlyerPage — Plan 21 baseline behavior preserved", () => {
  it("rejects empty title", async () => {
    renderWithProviders(<NewFlyerPage />);
    await userEvent.click(
      screen.getByRole("button", { name: /generate/i }),
    );
    // Default subtype is "event", so the event-required fields drive the
    // initial validation surface. zod v4 message: "Too small: expected
    // string to have >=1 characters". Multiple FormMessage nodes surface the
    // same message — getAllByText tolerates that.
    await waitFor(() => {
      const matches = screen.getAllByText(
        /at least 1|too small|required|must contain|invalid/i,
      );
      expect(matches.length).toBeGreaterThan(0);
    });
  });

  it("submits an event flyer with preset duplicated into event.style_preset", async () => {
    let captured: {
      event?: Record<string, unknown>;
      template?: string;
      preset?: string;
    } | null = null;
    server.use(
      http.post("/api/v1/flyers", async ({ request }) => {
        captured = (await request.json()) as {
          event: Record<string, unknown>;
          template: string;
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
    await userEvent.type(
      screen.getByLabelText(/style concept/i),
      "moody industrial",
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
    // Default template is "editorial_classic" (Phase 22).
    expect(captured!.template).toBe("editorial_classic");
    // Default subtype is "event".
    expect(captured!.event!.subtype).toBe("event");
  });
});

describe("NewFlyerPage — Phase 22 template + subtype", () => {
  it("renders template Select with 6 options", async () => {
    renderWithProviders(<NewFlyerPage />);
    const trigger = await screen.findByTestId("template-select");
    await userEvent.click(trigger);
    // Radix Select renders SelectContent in a portal — query the open
    // listbox specifically. The trigger also contains the current value text
    // (e.g. "editorial_classic"), so a global findByText would match both
    // the trigger and the option ("Found multiple elements").
    const listbox = await screen.findByRole("listbox");
    for (const t of [
      "editorial_classic",
      "bold_modern",
      "minimal_photo",
      "retro_poster",
      "zine",
      "tight_typographic",
    ]) {
      expect(within(listbox).getByText(t)).toBeInTheDocument();
    }
  });

  it("renders subtype Select with event + info", async () => {
    renderWithProviders(<NewFlyerPage />);
    const trigger = await screen.findByTestId("subtype-select");
    await userEvent.click(trigger);
    // SelectContent options live in a portal — both "event" and "info"
    // become DOM nodes when the dropdown opens.
    const listbox = await screen.findByRole("listbox");
    expect(within(listbox).getByText("event")).toBeInTheDocument();
    expect(within(listbox).getByText("info")).toBeInTheDocument();
  });

  it("default subtype is event; event fields shown, info fields hidden", async () => {
    renderWithProviders(<NewFlyerPage />);
    expect(await screen.findByLabelText(/^date$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^time$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/venue name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/venue address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^fees$/i)).toBeInTheDocument();
    // Info-only fields hidden:
    expect(screen.queryByLabelText(/description/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/call to action/i)).not.toBeInTheDocument();
  });

  it("switching to info hides event fields and shows description + CTA", async () => {
    renderWithProviders(<NewFlyerPage />);
    const trigger = await screen.findByTestId("subtype-select");
    await userEvent.click(trigger);
    const listbox = await screen.findByRole("listbox");
    await userEvent.click(within(listbox).getByText("info"));
    // Event fields gone:
    expect(screen.queryByLabelText(/^date$/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^time$/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/venue name/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/venue address/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^fees$/i)).not.toBeInTheDocument();
    // Info-only fields appeared:
    expect(await screen.findByLabelText(/description/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/call to action/i)).toBeInTheDocument();
  });

  it("submitting an info flyer sends the info payload (no event fields)", async () => {
    let captured: {
      event?: Record<string, unknown>;
      template?: string;
      preset?: string;
    } | null = null;
    server.use(
      http.post("/api/v1/flyers", async ({ request }) => {
        captured = (await request.json()) as {
          event: Record<string, unknown>;
          template: string;
          preset: string;
        };
        return HttpResponse.json(
          { job_id: "01J9ABCDEFGHJKMNPQRSTVWXYZ" },
          { status: 202 },
        );
      }),
    );

    renderWithProviders(<NewFlyerPage />);
    await userEvent.type(screen.getByLabelText(/^title$/i), "Notice");

    // Switch subtype to "info"
    const subtypeTrigger = await screen.findByTestId("subtype-select");
    await userEvent.click(subtypeTrigger);
    const listbox = await screen.findByRole("listbox");
    await userEvent.click(within(listbox).getByText("info"));

    await userEvent.type(
      screen.getByLabelText(/description/i),
      "Road closure on Main St",
    );
    await userEvent.type(
      screen.getByLabelText(/style concept/i),
      "civic",
    );

    await userEvent.click(
      screen.getByRole("button", { name: /generate/i }),
    );

    await screen.findByText(/flyer enqueued/i);
    expect(captured).not.toBeNull();
    expect(captured!.event!.subtype).toBe("info");
    expect(captured!.event!.description).toBe("Road closure on Main St");
    // Event-only fields are stripped to null on info submit.
    expect(captured!.event!.date).toBeNull();
    expect(captured!.event!.time).toBeNull();
    expect(captured!.event!.location_name).toBeNull();
    expect(captured!.event!.location_address).toBeNull();
    expect(captured!.event!.fees).toBeNull();
    expect(captured!.template).toBe("editorial_classic");
  });
});
