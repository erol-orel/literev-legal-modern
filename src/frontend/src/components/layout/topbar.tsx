import { Menu } from "lucide-react";

import { ThemeToggle } from "@/components/layout/theme-toggle";
import { UserMenu } from "@/components/layout/user-menu";
import { Button } from "@/components/ui/button";
import { useAppContext } from "@/hooks/use-app-context";

export function Topbar({ onOpenNav }: { onOpenNav: () => void }) {
  const { user } = useAppContext();

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur lg:px-8">
      <Button
        variant="ghost"
        size="icon"
        className="lg:hidden"
        onClick={onOpenNav}
        aria-label="Open navigation"
      >
        <Menu className="size-5" />
      </Button>

      <div className="ml-auto flex items-center gap-1">
        <ThemeToggle />
        {user.isAuthenticated && <UserMenu />}
      </div>
    </header>
  );
}
