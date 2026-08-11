import { Badge } from "@/components/ui/badge";
import { confidenceVariant } from "@/lib/confidence";
import { cn } from "@/lib/utils";

export function ConfidenceBadge({
  score,
  className,
}: {
  score: number;
  className?: string;
}) {
  return (
    <Badge variant={confidenceVariant(score)} className={className}>
      {Math.round(score * 100)}% confidence
    </Badge>
  );
}

/** A calm horizontal meter for the aggregate confidence of an answer. */
export function ConfidenceMeter({ score }: { score: number }) {
  const pct = Math.round(Math.min(1, Math.max(0, score)) * 100);
  const variant = confidenceVariant(score);
  const fill =
    variant === "success"
      ? "bg-success"
      : variant === "warning"
        ? "bg-warning"
        : "bg-muted-foreground";
  return (
    <div className="flex items-center gap-3">
      <div
        className="h-2 flex-1 overflow-hidden rounded-full bg-secondary"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Answer confidence"
      >
        <div className={cn("h-full rounded-full", fill)} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-xs tabular-nums text-foreground">{pct}%</span>
    </div>
  );
}
