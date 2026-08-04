import { History, Loader, Search, X } from "lucide-react";
import { NavLink } from "react-router-dom";

import { Logo } from "@/components/layout/logo";
import { Button } from "@/components/ui/button";
import { useAppContext } from "@/hooks/use-app-context";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: typeof Search;
  description: string;
}

export function Sidebar({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { urls, appVersion } = useAppContext();

  const items: NavItem[] = [
    {
      to: urls.search,
      label: "New search",
      icon: Search,
      description: "Start a legal-decision analysis",
    },
    {
      to: urls.running,
      label: "Running",
      icon: Loader,
      description: "Projects in progress",
    },
    {
      to: urls.historicalpage,
      label: "History",
      icon: History,
      description: "Completed projects",
    },
  ];

  return (
    <>
      {/* Mobile scrim */}
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/50 backdrop-blur-sm transition-opacity lg:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-sidebar text-sidebar-foreground transition-transform lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center justify-between px-5">
          <NavLink to={urls.search} onClick={onClose}>
            <Logo />
          </NavLink>
          <Button
            variant="ghost"
            size="icon"
            className="text-sidebar-foreground hover:bg-white/10 hover:text-white lg:hidden"
            onClick={onClose}
            aria-label="Close navigation"
          >
            <X className="size-5" />
          </Button>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  "group flex items-start gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                  isActive
                    ? "bg-white/10 text-white"
                    : "text-sidebar-foreground hover:bg-white/5 hover:text-white",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon
                    className={cn(
                      "mt-0.5 size-[1.15rem] shrink-0",
                      isActive
                        ? "text-sidebar-accent"
                        : "text-sidebar-foreground/70 group-hover:text-white",
                    )}
                  />
                  <span className="flex flex-col">
                    <span className="font-medium leading-tight">
                      {item.label}
                    </span>
                    <span className="text-xs text-sidebar-foreground/60">
                      {item.description}
                    </span>
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-sidebar-border px-5 py-4">
          <p className="text-xs text-sidebar-foreground/50">
            LiteRev Legal{appVersion ? ` · v${appVersion}` : ""}
          </p>
        </div>
      </aside>
    </>
  );
}
