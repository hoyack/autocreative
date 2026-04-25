// Plan 23-05 Task 2 — failing tests for the postcard creator form.
//
// Mirrors brochures/new.test.tsx but adapted to PostcardCreateRequest's
// flat shape (headline + body + template + optional address_block). The
// form ships a Switch that reveals/hides the 3 address sub-fields; the
// default render must NOT show them (T-23-19 mitigation: zod refine
// requires all 3 when toggle is on).
import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { server } from "@/test/msw-server";
import { renderWithProviders } from "@/test/test-utils";

import { NewPostcardPage } from "./new";

describe("NewPostcardPage", () => {
  it("renders headline, body, and template fields", () => {
    renderWithProviders(<NewPostcardPage />);
    expect(screen.getByLabelText(/headline/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^body$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/template/i)).toBeInTheDocument();
  });

  it("renders the editorial page header (08 / The Mail)", () => {
    renderWithProviders(<NewPostcardPage />);
    // PageHeader composes "08 / THE MAIL" from number + kicker; assert
    // both visible pieces are present in the rendered tree.
    expect(screen.getByText("08")).toBeInTheDocument();
    expect(screen.getByText(/the mail/i)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /new postcard/i }),
    ).toBeInTheDocument();
  });

  it("renders the Generate postcard submit button", () => {
    renderWithProviders(<NewPostcardPage />);
    expect(
      screen.getByRole("button", { name: /generate postcard/i }),
    ).toBeInTheDocument();
  });

  it("hides address-block fields by default", () => {
    renderWithProviders(<NewPostcardPage />);
    expect(
      screen.queryByLabelText(/recipient name/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^street$/i)).not.toBeInTheDocument();
  });

  it("submits the body to /api/v1/postcards and toasts the job id", async () => {
    let captured: Record<string, unknown> | null = null;
    server.use(
      http.post("/api/v1/postcards", async ({ request }) => {
        captured = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { job_id: "01J9ABCDEFGHJKMNPQRSTVWXYZ" },
          { status: 202 },
        );
      }),
    );
    renderWithProviders(<NewPostcardPage />);
    await userEvent.type(
      screen.getByLabelText(/headline/i),
      "Save the date",
    );
    await userEvent.type(
      screen.getByLabelText(/^body$/i),
      "Hello world.",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /generate postcard/i }),
    );
    await screen.findByText(/postcard enqueued/i);
    expect(captured).toBeTruthy();
    const body = captured as unknown as {
      headline: string;
      body: string;
      template: string;
      address_block: unknown;
    };
    expect(body.headline).toBe("Save the date");
    expect(body.body).toBe("Hello world.");
    expect(body.template).toBe("classic_portrait");
    // Address-block toggle off by default — body sends null.
    expect(body.address_block).toBeNull();
  });
});
