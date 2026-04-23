// Per 21-RESEARCH.md Pattern 6 (lines 1022-1032) VERBATIM.
//
// CRITICAL (21-RESEARCH.md Pitfall #10): onUnhandledRequest MUST be "error" —
// msw v2 defaults to "warn" which lets tests silently pass with empty data
// when they hit an unmocked endpoint, then fail mysteriously elsewhere.
import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./msw-server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
