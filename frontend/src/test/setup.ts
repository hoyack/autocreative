// Per 21-RESEARCH.md Pattern 6 (lines 1022-1032).
//
// CRITICAL (21-RESEARCH.md Pitfall #10): onUnhandledRequest MUST be "error" —
// msw v2 defaults to "warn" which lets tests silently pass with empty data
// when they hit an unmocked endpoint, then fail mysteriously elsewhere.
//
// Note: the relative-URL problem that openapi-fetch hits in Node is handled
// inside `src/api/client.ts` itself (it reads `globalThis.location.origin`
// so jsdom supplies an absolute base) rather than here.
//
// [Rule 3 - Blocking] openapi-fetch captures `globalThis.fetch` at
// `createClient()` time (see node_modules/openapi-fetch/src/index.js:28
// `baseFetch = globalThis.fetch`). msw's `server.listen()` patches
// globalThis.fetch but only runs inside `beforeAll`. If we rely on beforeAll,
// client.ts is imported first (top-level test import) and captures the
// *un-patched* fetch — which then issues real network requests and fails
// with ECONNREFUSED. Fix: call server.listen() at top-level here (setupFiles
// run before test-file imports) so msw hooks fetch before any module
// captures it. Keep the afterEach/afterAll lifecycle hooks so handlers reset
// between tests and the server cleans up at the end of the worker.
import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, vi } from "vitest";
import { server } from "./msw-server";

// [Plan 21-05 Rule 3 - Blocking] jsdom does not implement window.matchMedia.
// sonner's <Toaster /> calls matchMedia at mount time (to detect prefers-
// color-scheme), so any test that renders a route which eventually surfaces
// a toast (e.g. the new ScrapeBrandKitPage success branch) throws
// "window.matchMedia is not a function". Polyfill a no-op MediaQueryList
// before any component mount.
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

// [Plan 21-09 Rule 3 - Blocking] jsdom does not implement ResizeObserver.
// @radix-ui/react-checkbox (via @radix-ui/react-use-size) calls new
// ResizeObserver(...) at mount to track its indicator size. Without this
// polyfill, any test that renders a route containing a ShadCN Checkbox
// (plan 21-09's NewCampaignPage platforms multi-select) throws
// "ResizeObserver is not defined". A no-op class satisfies the surface
// area Radix uses (observe / unobserve / disconnect).
if (typeof globalThis.ResizeObserver === "undefined") {
  class NoopResizeObserver implements ResizeObserver {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  (globalThis as unknown as { ResizeObserver: typeof ResizeObserver }).ResizeObserver =
    NoopResizeObserver as unknown as typeof ResizeObserver;
}

server.listen({ onUnhandledRequest: "error" });
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
