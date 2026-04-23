// Per 21-04-PLAN.md Task 3 step 3. Covers the two most fragile branches of
// JobStatusCard:
//   1. Succeeded + string result_ref -> renders <img> via RenderPreview
//   2. Failed + error_detail -> renders a <pre> with the serialized error
//      AND shows a "failed" badge.
//
// RED gate: these tests fail until JobStatusCard.tsx is written.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import { server } from "@/test/msw-server";
import { renderWithProviders } from "@/test/test-utils";
import { JobStatusCard } from "./JobStatusCard";

describe("JobStatusCard", () => {
  it("renders an <img> for a succeeded job with a single PNG result_ref", async () => {
    // Default msw handler returns succeeded + a /renders/.../image URL.
    renderWithProviders(
      <JobStatusCard jobId="01J9ABCDEFGHJKMNPQRSTVWXYZ" />,
    );
    const img = await screen.findByRole("img", { name: /render/i });
    expect(img).toHaveAttribute(
      "src",
      "/api/v1/renders/01J9ABCDEFGHJKMNPQRSTVWXYZ/image",
    );
  });

  it("renders the error_detail in a <pre> when status is failed", async () => {
    server.use(
      http.get("/api/v1/jobs/:id", ({ params }) =>
        HttpResponse.json({
          id: params.id,
          kind: "flyer",
          status: "failed",
          started_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
          error_detail: {
            type: "ComfyError",
            message: "background generation timeout",
          },
          result_ref: null,
          created_at: new Date().toISOString(),
        }),
      ),
    );
    renderWithProviders(<JobStatusCard jobId="01FAIL" />);
    const pre = await screen.findByText(/background generation timeout/);
    expect(pre.tagName.toLowerCase()).toBe("pre");
    // Failed badge — the Badge component renders the string "failed".
    expect(screen.getByText(/failed/i)).toBeInTheDocument();
  });
});
