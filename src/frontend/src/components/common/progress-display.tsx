import { Loader2 } from "lucide-react";

import { Progress } from "@/components/ui/progress";
import type { ProjectProgress } from "@/api/projects";
import { clampPercent } from "@/lib/utils";

/** Render a project's ProjectProgress union: a bar or an indeterminate pill. */
export function ProgressDisplay({ progress }: { progress: ProjectProgress }) {
  if (progress.kind === "progress") {
    const pct = clampPercent(progress.percentage);
    return (
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{progress.message}</span>
          <span className="font-medium text-foreground">{progress.label}</span>
        </div>
        <Progress value={pct} aria-label={progress.message} />
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <Loader2 className="size-3.5 animate-spin text-primary" />
      <span>{progress.message}</span>
    </div>
  );
}
