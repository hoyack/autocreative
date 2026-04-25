// Source: https://openapi-ts.dev/openapi-fetch/
// Per 21-RESEARCH.md Pattern 2 + Pitfall #6: the client's effective URL
// should be same-origin so the Vite dev proxy (vite.config.ts forwards /api/*
// to http://localhost:8000) and eventual same-origin production mount both
// work without client-side URL rewriting. Set VITE_API_URL only when
// pointing at a non-default backend.
//
// [21-04 Rule 3 Blocking fix] baseUrl resolution order:
//   1. import.meta.env.VITE_API_URL (explicit override, e.g. staging backend)
//   2. globalThis.location?.origin (the same origin the browser is on — in
//      the real browser this is :5173/dev or the prod host; in jsdom tests
//      it's http://localhost:3000; openapi-fetch's `new URL(path, base)`
//      requires an ABSOLUTE base and rejects "" with ERR_INVALID_URL,
//      which is what killed useJob tests before this fix).
//   3. "" (pure Node SSR fallback — shouldn't happen for an SPA)
// In every real environment path 2 is taken, so the behavior is equivalent
// to the old "relative" setup: every URL the client sends is same-origin.
//
// IMPORTANT: Path keys below are the ABSOLUTE paths emitted by FastAPI's
// /openapi.json — FastAPI bakes the `prefix="/api/v1"` mount (see
// flyer_generator/api/__init__.py:39) into every path in the OpenAPI doc, so
// the generated `paths` type in schema.gen.ts is keyed by "/api/v1/flyers",
// NOT "/flyers". Downstream plans must call client.POST("/api/v1/flyers", ...)
// and use the absolute path aliases exported below — they match the generated
// types exactly.
import createClient from "openapi-fetch";
import type { paths } from "./schema.gen";

function resolveBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl && envUrl.length > 0) return envUrl;
  if (typeof globalThis !== "undefined" && globalThis.location?.origin) {
    return globalThis.location.origin;
  }
  return "";
}

export const client = createClient<paths>({
  baseUrl: resolveBaseUrl(),
});

// Re-export the root paths type so consumers can derive custom subtypes.
export type Schemas = paths;

// --- Request body aliases --------------------------------------------
export type BrandKitFetchRequestBody =
  paths["/api/v1/brand-kits/fetch"]["post"]["requestBody"]["content"]["application/json"];

export type FlyerCreateRequestBody =
  paths["/api/v1/flyers"]["post"]["requestBody"]["content"]["application/json"];

export type BrochureCreateRequestBody =
  paths["/api/v1/brochures"]["post"]["requestBody"]["content"]["application/json"];

export type PostcardCreateRequestBody =
  paths["/api/v1/postcards"]["post"]["requestBody"]["content"]["application/json"];

export type PostcardDetail =
  paths["/api/v1/postcards/{postcard_id}"]["get"]["responses"][200]["content"]["application/json"];

export type PosterCreateRequestBody =
  paths["/api/v1/posters"]["post"]["requestBody"]["content"]["application/json"];

export type PostCreateRequestBody =
  paths["/api/v1/social/posts"]["post"]["requestBody"]["content"]["application/json"];

export type CampaignCreateRequestBody =
  paths["/api/v1/social/campaigns"]["post"]["requestBody"]["content"]["application/json"];

// --- Response aliases ------------------------------------------------
export type JobCreated =
  paths["/api/v1/flyers"]["post"]["responses"][202]["content"]["application/json"];

export type JobDetail =
  paths["/api/v1/jobs/{job_id}"]["get"]["responses"][200]["content"]["application/json"];

export type PaginatedBrandKits =
  paths["/api/v1/brand-kits"]["get"]["responses"][200]["content"]["application/json"];

export type BrandKitDetail =
  paths["/api/v1/brand-kits/{slug}"]["get"]["responses"][200]["content"]["application/json"];

// --- Error body shape (stable across all 4xx/5xx, per errors.py) ----
// Kept as a hand-written interface because openapi-typescript does not
// currently emit a single shared type for FastAPI error responses.
export interface ApiErrorBody {
  detail: string | unknown;
  error_type: string;
  trace_id: string;
}

// --- Status enum literals (mirror flyer_generator/api/models/job.py) -
// Narrowed so `isTerminal(status)` below is typesafe.
export const TERMINAL_STATUSES = ["succeeded", "failed", "cancelled"] as const;
export type TerminalStatus = (typeof TERMINAL_STATUSES)[number];

export function isTerminalStatus(s: unknown): s is TerminalStatus {
  return (
    typeof s === "string" &&
    (TERMINAL_STATUSES as readonly string[]).includes(s)
  );
}
