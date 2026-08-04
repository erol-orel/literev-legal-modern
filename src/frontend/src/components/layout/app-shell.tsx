import { useState } from "react";
import { Outlet } from "react-router-dom";

import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { RequireAuth } from "@/components/auth/require-auth";

/** Authenticated application shell: fixed sidebar + top bar + routed content. */
export function AppShell() {
  const [navOpen, setNavOpen] = useState(false);

  return (
    <RequireAuth>
      <div className="min-h-screen bg-background">
        <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />
        <div className="flex min-h-screen flex-col lg:pl-64">
          <Topbar onOpenNav={() => setNavOpen(true)} />
          <main className="flex-1 px-4 py-6 lg:px-8 lg:py-8">
            <div className="mx-auto w-full max-w-6xl animate-fade-in">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </RequireAuth>
  );
}
