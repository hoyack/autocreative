// src/lib/elapsed.ts
// Per 21-RESEARCH.md "Code Examples" (lines 1158-1168) VERBATIM.
// Hand-rolled ms-to-human formatter. ~5 lines, no date-fns dep.
export function formatElapsed(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${s % 60}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}
