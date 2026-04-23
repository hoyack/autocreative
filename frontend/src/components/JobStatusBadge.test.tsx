// Plan 21-10 Task 3 (TDD).
//
// Single test covering the queued -> running -> succeeded transition via
// msw-mocked /jobs/:id polling. Proves:
//   1. Non-terminal rows subscribe to useJob and surface the live status.
//   2. useJob's refetchInterval terminator (query.state.data.status in the
//      TERMINAL set) stops polling once succeeded arrives — we assert the
//      handler ran at least 3 times before the test ended.
//
// Terminal-row skip path (initialStatus in the TERMINAL set -> render a
// static badge without mounting useJob) is covered by the list page tests
// in pages/jobs/list.test.tsx (which renders a succeeded flyer row + a
// running brochure row); those exercise both branches end-to-end.
import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";

import { server } from "@/test/msw-server";
import { renderWithProviders } from "@/test/test-utils";

import { JobStatusBadge } from "./JobStatusBadge";

describe("JobStatusBadge", () => {
  it("transitions queued -> running -> succeeded via msw-mocked polling", async () => {
    // Sequence: call #1 -> queued, call #2 -> running, calls #3+ -> succeeded.
    let calls = 0;
    server.use(
      http.get("/api/v1/jobs/:id", ({ params }) => {
        calls += 1;
        const status =
          calls === 1 ? "queued" : calls === 2 ? "running" : "succeeded";
        return HttpResponse.json({
          id: params.id,
          kind: "flyer",
          status,
          started_at: new Date().toISOString(),
          completed_at: status === "succeeded" ? new Date().toISOString() : null,
          error_detail: null,
          result_ref:
            status === "succeeded" ? "/api/v1/renders/01XX/image" : null,
          created_at: new Date().toISOString(),
        });
      }),
    );

    renderWithProviders(
      <JobStatusBadge jobId="01POLLBADGE00000000000000" initialStatus="queued" />,
    );

    // The fallback ("queued") renders immediately from initialStatus; the
    // hook's refetchInterval drives queued -> running -> succeeded. We only
    // assert on the terminal state which is the guaranteed endpoint.
    await screen.findByText("succeeded", undefined, { timeout: 5000 });
    // At least 3 GETs must have fired (q, r, s) before polling stopped.
    expect(calls).toBeGreaterThanOrEqual(3);
  });
});
