// Per 21-RESEARCH.md Pattern 6 (lines 1004-1020, VERBATIM).
// Per 21-RESEARCH.md Pitfall #8: do NOT preemptively add
// optimizeDeps: { exclude: ["msw"] } — only add it if a concrete msw/node
// "module not found" error surfaces.
//
// The relative-URL + Node-undici-fetch issue is handled in
// src/test/setup.ts via a fetch wrapper (see that file's header comment).
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
