// Per 21-RESEARCH.md Pattern 6 (lines 1063-1079) + plan 21-05 extension.
//
// renderWithProviders wraps a unit-under-test in QueryClientProvider +
// MemoryRouter + <Toaster /> so components that call useJob / useNavigate /
// useParams / toast.success render correctly in jsdom without needing a real
// browser router or a project-wide QueryClient.
//
// The Toaster is mounted OUTSIDE the MemoryRouter (same position it holds in
// main.tsx) so that toast calls from within a routed page surface as real
// DOM nodes findable via screen.findByText(...). Plan 21-05's new-page test
// needs this for "Scrape enqueued" assertion.
import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import type { ReactElement, ReactNode } from "react";

import { Toaster } from "@/components/ui/sonner";

export function renderWithProviders(
  ui: ReactElement,
  options?: RenderOptions,
) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
      <Toaster />
    </QueryClientProvider>
  );
  return render(ui, { wrapper: Wrapper, ...options });
}
