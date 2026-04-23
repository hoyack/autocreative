// Plan 21-07 Task 2 — failing tests for the brochure creator form.
//
// The form accepts a JSON-paste Textarea (per 21-RESEARCH.md fallback
// recommendation lines 336-348) plus template/brand_kit/workflow/style_preset
// inputs + a Switch for generate_images. Submits to POST /api/v1/brochures
// and navigates to /brochures/:job_id on success.
import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { server } from "@/test/msw-server";
import { renderWithProviders } from "@/test/test-utils";

import { NewBrochurePage } from "./new";

describe("NewBrochurePage", () => {
  it("rejects malformed JSON in the content textarea", async () => {
    renderWithProviders(<NewBrochurePage />);
    const textarea = screen.getByLabelText(/content/i);
    await userEvent.clear(textarea);
    // Malformed JSON — missing closing brace.
    await userEvent.type(textarea, "{not valid");
    await userEvent.click(
      screen.getByRole("button", { name: /generate/i }),
    );
    // zod .refine() surfaces a validation message on the field.
    const matches = await screen.findAllByText(/must be valid json/i);
    expect(matches.length).toBeGreaterThan(0);
  });

  it("submits the parsed content as the body.content field", async () => {
    let captured: Record<string, unknown> | null = null;
    server.use(
      http.post("/api/v1/brochures", async ({ request }) => {
        captured = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { job_id: "01J9ABCDEFGHJKMNPQRSTVWXYZ" },
          { status: 202 },
        );
      }),
    );
    renderWithProviders(<NewBrochurePage />);
    // Default sample JSON satisfies zod's refine; just submit.
    await userEvent.click(
      screen.getByRole("button", { name: /generate/i }),
    );
    await screen.findByText(/brochure enqueued/i);
    expect(captured).toBeTruthy();
    // Narrow via type guard so TS accepts the following property accesses.
    const body = captured as {
      template: string;
      content: { title: string };
    };
    expect(body.template).toBe("editorial_classic");
    expect(typeof body.content).toBe("object");
    expect(body.content.title).toBe("Sample brochure");
  });
});
