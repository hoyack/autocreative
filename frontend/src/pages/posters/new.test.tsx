// Plan 24-05 Task 2 — tests for the poster creator form (PO-04).
//
// Mirrors postcards/new.test.tsx structurally. Substitutes:
//   * Postcard -> Poster
//   * "08 / The Mail" -> "09 / The Big One"
//   * Body field -> Size + Template Selects
// Adds a 4th case asserting the size Select default is "18x24" and a 5th
// case asserting the end-to-end POST body shape.
import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { server } from "@/test/msw-server";
import { renderWithProviders } from "@/test/test-utils";

import { NewPosterPage } from "./new";

describe("NewPosterPage", () => {
  it("renders headline + size + template fields by accessible label", () => {
    renderWithProviders(<NewPosterPage />);
    expect(screen.getByLabelText(/headline/i)).toBeInTheDocument();
    // Radix <Select> trigger: the Label is associated via FormField but the
    // trigger itself is keyed by data-testid for stable assertions across
    // CSS-in-JS internals (mirrors flyer creator's template-select pattern).
    expect(screen.getByTestId("size-select")).toBeInTheDocument();
    expect(screen.getByTestId("template-select")).toBeInTheDocument();
  });

  it("renders the editorial page header (09 / The Big One)", () => {
    renderWithProviders(<NewPosterPage />);
    // PageHeader composes "09 / THE BIG ONE" from number + kicker; assert
    // each visible piece is present in the rendered tree separately.
    expect(screen.getByText("09")).toBeInTheDocument();
    expect(screen.getByText(/the big one/i)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /new poster/i }),
    ).toBeInTheDocument();
  });

  it("renders the Generate poster submit button", () => {
    renderWithProviders(<NewPosterPage />);
    expect(
      screen.getByRole("button", { name: /generate poster/i }),
    ).toBeInTheDocument();
  });

  it("defaults the size Select to 18x24", () => {
    renderWithProviders(<NewPosterPage />);
    // Radix trigger renders the selected value as text content; assert the
    // default '18x24' is displayed without opening the dropdown.
    expect(screen.getByTestId("size-select")).toHaveTextContent(/18x24/i);
  });

  it("submits POST to /api/v1/posters with the correct body shape", async () => {
    let captured: Record<string, unknown> | null = null;
    server.use(
      http.post("/api/v1/posters", async ({ request }) => {
        captured = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { job_id: "01HBQX01ZZZZZZZZZZZZZZZZZZ" },
          { status: 202 },
        );
      }),
    );
    renderWithProviders(<NewPosterPage />);
    await userEvent.type(
      screen.getByLabelText(/headline/i),
      "Friday Night Show",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /generate poster/i }),
    );
    await screen.findByText(/poster enqueued/i);
    expect(captured).toBeTruthy();
    const body = captured as unknown as {
      headline: string;
      template: string;
      size: string;
      style_preset: string;
      subheading: string | null;
      cta_text: string | null;
      image_hint: string | null;
      brand_kit_slug: string | null;
    };
    expect(body.headline).toBe("Friday Night Show");
    // Defaults from useForm.defaultValues should land on the wire.
    expect(body.template).toBe("editorial_grand");
    expect(body.size).toBe("18x24");
    expect(body.style_preset).toBe("photorealistic");
    // Empty-string optional fields normalize to null per mutationFn contract
    // (mirrors backend Pydantic Optional[str] = None semantics).
    expect(body.subheading).toBeNull();
    expect(body.cta_text).toBeNull();
    expect(body.image_hint).toBeNull();
    expect(body.brand_kit_slug).toBeNull();
  });
});
