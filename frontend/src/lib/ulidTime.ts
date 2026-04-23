// src/lib/ulidTime.ts
// Per 21-RESEARCH.md "Code Examples" (lines 1170-1180) VERBATIM.
// Wrapper for the `ulid` package's decodeTime() that returns null on invalid
// input instead of throwing — simpler to use in JSX that might see a garbage
// id from a route param.
import { decodeTime } from "ulid";

export function ulidToDate(id: string): Date | null {
  try {
    return new Date(decodeTime(id));
  } catch {
    return null;
  }
}
