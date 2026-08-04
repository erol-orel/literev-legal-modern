import { Scale } from "lucide-react";

import { cn } from "@/lib/utils";

/** LiteRev wordmark with a scales-of-justice glyph. */
export function Logo({
  className,
  onDark = true,
}: {
  className?: string;
  onDark?: boolean;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <span
        className={cn(
          "flex size-8 items-center justify-center rounded-md",
          onDark ? "bg-white/10 text-white" : "bg-primary/10 text-primary",
        )}
      >
        <Scale className="size-[1.15rem]" />
      </span>
      <span
        className={cn(
          "text-lg font-semibold tracking-tight",
          onDark ? "text-white" : "text-foreground",
        )}
      >
        Lite<span className="font-bold text-sidebar-accent">Rev</span>
      </span>
    </span>
  );
}
