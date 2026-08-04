import { QueryClient } from "@tanstack/react-query";

/**
 * Shared TanStack Query client. Retries are disabled because these endpoints
 * are user-scoped and mutate real projects — a failed request should surface,
 * not silently repeat — and window-focus refetches are off so long-lived pages
 * (project overview, RAG) don't reload on every tab switch. Pages that need
 * freshness opt in with their own `refetchInterval`.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});
