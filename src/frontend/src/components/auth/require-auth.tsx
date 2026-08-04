import type { ReactNode } from "react";

import { useAppContext } from "@/hooks/use-app-context";

/**
 * Client-side mirror of Django's `LoginRequiredMixin`. Django remains the
 * source of truth for access control; this only avoids flashing an
 * authenticated shell before the server redirect completes.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, urls } = useAppContext();

  if (!user.isAuthenticated) {
    const next = window.location.pathname + window.location.search;
    window.location.assign(`${urls.login}?next=${encodeURIComponent(next)}`);
    return null;
  }

  return <>{children}</>;
}
