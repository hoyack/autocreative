/**
 * Central registry of TanStack Query keys.
 *
 * Rationale (21-PATTERNS.md "Pattern: TanStack Query key registry"):
 *   - Every `useQuery` / `useMutation` references this registry, never a
 *     hard-coded array literal.
 *   - `invalidateQueries({ queryKey: queryKeys.jobs() })` stays type-safe
 *     and greppable.
 *   - Keys are `as const` tuples so TanStack Query's key hashing is stable.
 */

export const queryKeys = {
  // Singular job (polled via useJob hook — plan 21-04)
  job: (id: string) => ["job", id] as const,
  // Paginated jobs list (plan 21-10)
  jobs: (filters?: {
    kind?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }) => ["jobs", filters ?? {}] as const,
  // Paginated brand-kits list (plan 21-05)
  brandKits: (filters?: { limit?: number; offset?: number }) =>
    ["brand-kits", filters ?? {}] as const,
  // Single brand-kit detail (plan 21-05)
  brandKit: (slug: string) => ["brand-kit", slug] as const,
  // Paginated renders gallery (plan 21-11)
  renders: (filters?: {
    kind?: string;
    since?: string;
    limit?: number;
    offset?: number;
  }) => ["renders", filters ?? {}] as const,
  // Brochure detail — 3-artifact fuse (plan 21-07)
  brochure: (id: string) => ["brochure", id] as const,
} as const;

export type QueryKeys = typeof queryKeys;
