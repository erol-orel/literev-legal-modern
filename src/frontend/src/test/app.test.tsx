import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it } from "vitest";

import { App } from "@/app/app";
import { ThemeProvider } from "@/hooks/use-theme";
import { TooltipProvider } from "@/components/ui/tooltip";
import { __setAppContextForTests } from "@/lib/context";

function renderApp(initialPath: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <TooltipProvider>
          <MemoryRouter initialEntries={[initialPath]}>
            <App />
          </MemoryRouter>
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>,
  );
}

describe("App routing", () => {
  beforeEach(() => {
    __setAppContextForTests(null);
  });

  it("shows the landing page for anonymous visitors", () => {
    __setAppContextForTests({ user: { isAuthenticated: false, email: "" } });
    renderApp("/");
    expect(
      screen.getByRole("heading", {
        name: /search, cluster and question french legal decisions/i,
      }),
    ).toBeInTheDocument();
  });

  it("renders the search page for authenticated users", () => {
    __setAppContextForTests({
      user: { isAuthenticated: true, email: "lawyer@example.com" },
    });
    renderApp("/search/");
    expect(
      screen.getByRole("heading", { name: /new search/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/project name/i)).toBeInTheDocument();
  });
});
