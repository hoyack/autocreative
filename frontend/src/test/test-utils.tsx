// Per 21-RESEARCH.md Pattern 6 (lines 1063-1079) VERBATIM.
//
// renderWithProviders wraps a unit-under-test in QueryClientProvider +
// MemoryRouter so components that call useJob / useNavigate / useParams
// render correctly in jsdom without needing a real browser router or a
// project-wide QueryClient.
import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import type { ReactElement, ReactNode } from "react";

export function renderWithProviders(
  ui: ReactElement,
  options?: RenderOptions,
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
  return render(ui, { wrapper: Wrapper, ...options });
}
