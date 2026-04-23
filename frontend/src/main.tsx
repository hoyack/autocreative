import "./index.css";
import React from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/sonner";
import { router } from "./routes";

// Per 21-RESEARCH.md "main.tsx" pattern (Pattern 5, lines 968-997):
// - retry: 1 — soft retry on transient errors
// - refetchOnWindowFocus: false — polling drives freshness, not focus
// - mutations.retry: 0 — POSTs are not idempotent
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});

// Per 21-RESEARCH.md Open Question #6: <Toaster /> lives in main.tsx so toasts
// render even on routes outside the DashboardLayout (e.g. ErrorPage when the
// layout itself crashes).
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster richColors position="top-right" />
    </QueryClientProvider>
  </React.StrictMode>,
);
