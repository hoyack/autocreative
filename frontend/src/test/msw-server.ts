// Per 21-04-PLAN.md Task 2 step 4.
//
// The openapi-fetch client is configured with baseUrl: "" so the browser
// resolves every request against its origin (in dev: the Vite dev server
// proxies /api/* to FastAPI; in jsdom tests: localhost). msw v2's http.*
// handlers accept a relative path and match against the full URL regardless
// of the host — so using the relative "/api/v1/..." pattern here covers both
// environments without the test having to care about the hostname.
//
// Per-test overrides: call `server.use(http.get(...))` inside a test to
// override a default handler for that test only; setup.ts's afterEach calls
// resetHandlers() which restores the defaults between tests.
import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";

const BASE = "/api/v1";

export const handlers = [
  // Default: every job poll returns "succeeded" with a single PNG render URL.
  // Tests that need queued/running/failed override via server.use(...).
  http.get(`${BASE}/jobs/:id`, ({ params }) =>
    HttpResponse.json({
      id: params.id,
      kind: "flyer",
      status: "succeeded",
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      error_detail: null,
      result_ref: "/api/v1/renders/01J9ABCDEFGHJKMNPQRSTVWXYZ/image",
      created_at: new Date().toISOString(),
    }),
  ),
  // Default: every flyer enqueue returns 202 + a deterministic job id.
  http.post(`${BASE}/flyers`, async () =>
    HttpResponse.json(
      { job_id: "01J9ABCDEFGHJKMNPQRSTVWXYZ" },
      { status: 202 },
    ),
  ),
];

export const server = setupServer(...handlers);
