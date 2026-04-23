// Per 21-04-PLAN.md Task 2 step 7 — tests covering the 3 most-likely-bug
// paths for the useJob polling hook:
//   1. Response shape (a 200 resolves to a JobDetail with status)
//   2. Terminal stop (status="succeeded" returns refetchInterval=false,
//      fetchStatus settles to "idle")
//   3. Running continuation (status flips from "running" -> "succeeded";
//      hook polls ≥3 times until it lands on the terminal)
//
// CRITICAL: these tests fail RED until useJob.ts is written — that's the
// TDD gate for this plan.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { server } from "@/test/msw-server";
import { useJob } from "./useJob";

function wrap(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

describe("useJob", () => {
  it("returns the job detail on a 200 response", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const { result } = renderHook(
      () => useJob("01J9ABCDEFGHJKMNPQRSTVWXYZ"),
      { wrapper: wrap(client) },
    );
    await waitFor(() =>
      expect(result.current.data?.status).toBe("succeeded"),
    );
    expect(result.current.data?.id).toBe("01J9ABCDEFGHJKMNPQRSTVWXYZ");
  });

  it("stops polling once status is terminal (succeeded)", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const { result } = renderHook(() => useJob("01TEST"), {
      wrapper: wrap(client),
    });
    await waitFor(() =>
      expect(result.current.data?.status).toBe("succeeded"),
    );
    // The query is no longer scheduled to refetch: fetchStatus settles
    // to "idle" once refetchInterval callback returns false.
    const queryState = client
      .getQueryCache()
      .find({ queryKey: ["job", "01TEST"] });
    expect(queryState?.state.fetchStatus).toBe("idle");
  });

  it("keeps polling while status is running", async () => {
    // Override the default handler to return "running" on calls 1-2,
    // then "succeeded" on call 3+. Polling must drive us across that
    // transition and terminate.
    let calls = 0;
    server.use(
      http.get("/api/v1/jobs/:id", ({ params }) => {
        calls += 1;
        return HttpResponse.json({
          id: params.id,
          kind: "flyer",
          status: calls < 3 ? "running" : "succeeded",
          started_at: new Date().toISOString(),
          completed_at: calls < 3 ? null : new Date().toISOString(),
          error_detail: null,
          result_ref:
            calls < 3 ? null : "/api/v1/renders/01J9XXX/image",
          created_at: new Date().toISOString(),
        });
      }),
    );
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const { result } = renderHook(() => useJob("01POLL"), {
      wrapper: wrap(client),
    });
    // First, we observe "running".
    await waitFor(() =>
      expect(result.current.data?.status).toBe("running"),
    );
    // Eventually polling drives us to "succeeded".
    await waitFor(
      () => expect(result.current.data?.status).toBe("succeeded"),
      { timeout: 5000 },
    );
    expect(calls).toBeGreaterThanOrEqual(3);
  });
});
