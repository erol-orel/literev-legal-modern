import type { RagContext, RagDocumentAnswer } from "@/api/rag";
import { ConfidenceMeter } from "@/components/rag/confidence";
import { meanConfidence } from "@/lib/confidence";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type VerdictKey = "oui" | "non" | "peut_etre" | "mixte";

const VERDICT_LABEL: Record<VerdictKey, string> = {
  oui: "Oui",
  non: "Non",
  peut_etre: "Peut-être",
  mixte: "Mixte",
};

const VERDICT_BAR: Record<VerdictKey, string> = {
  oui: "bg-success",
  non: "bg-destructive",
  peut_etre: "bg-warning",
  mixte: "bg-muted-foreground",
};

const VERDICT_ORDER: VerdictKey[] = ["oui", "non", "peut_etre", "mixte"];

/**
 * The answer-first hero: the general summary reads as the lead, with the
 * closed-question verdict distribution, aggregate confidence, key
 * considerations and the rule of law grouped beneath it. This is the first
 * thing a jurist sees — the direct answer to their question.
 */
export function AnswerVerdict({
  context,
  answers,
}: {
  context: RagContext;
  answers: RagDocumentAnswer[];
}) {
  const current = context.current;
  if (!current) return null;

  const confidence = meanConfidence(answers);
  const dominant = current.show_closed_stats
    ? VERDICT_ORDER.reduce<VerdictKey | null>((best, key) => {
        if (best === null) return key;
        return current.counts[key] > current.counts[best] ? key : best;
      }, null)
    : null;

  return (
    <Card className="overflow-hidden">
      <div className="h-1 w-full bg-gradient-to-r from-primary/70 to-primary" />
      <CardContent className="space-y-5 pt-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            General summary
          </p>
          {dominant && (
            <Badge
              variant={
                dominant === "oui"
                  ? "success"
                  : dominant === "non"
                    ? "destructive"
                    : dominant === "peut_etre"
                      ? "warning"
                      : "muted"
              }
              className="text-sm"
            >
              {VERDICT_LABEL[dominant]} · {current.percentages[dominant]}%
            </Badge>
          )}
        </div>

        {current.summary_text ? (
          <p className="font-serif text-lg leading-relaxed text-foreground">
            {current.summary_text}
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">
            No general summary was produced for this question.
          </p>
        )}

        {current.show_closed_stats && (
          <div className="space-y-2">
            <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-secondary">
              {VERDICT_ORDER.map((key) =>
                current.percentages[key] > 0 ? (
                  <div
                    key={key}
                    className={cn("h-full", VERDICT_BAR[key])}
                    style={{ width: `${current.percentages[key]}%` }}
                    title={`${VERDICT_LABEL[key]} — ${current.counts[key]} (${current.percentages[key]}%)`}
                  />
                ) : null,
              )}
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              {VERDICT_ORDER.map((key) => (
                <div key={key} className="flex items-center gap-1.5 text-xs">
                  <span
                    className={cn("size-2 rounded-full", VERDICT_BAR[key])}
                    aria-hidden
                  />
                  <span className="text-muted-foreground">
                    {VERDICT_LABEL[key]}
                  </span>
                  <span className="font-medium tabular-nums text-foreground">
                    {current.counts[key]} ({current.percentages[key]}%)
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {confidence != null && (
          <div className="space-y-1.5 rounded-lg border bg-muted/30 p-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Answer confidence
              </p>
              <span className="text-xs text-muted-foreground">
                mean faithfulness across cited decisions
              </span>
            </div>
            <ConfidenceMeter score={confidence} />
          </div>
        )}

        {current.considerations.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Key considerations
            </p>
            <ul className="space-y-1.5">
              {current.considerations.slice(0, 8).map((consideration, index) => (
                <li
                  key={index}
                  className="flex items-start justify-between gap-3 text-sm"
                >
                  <span className="text-foreground/90">
                    {consideration.text}
                  </span>
                  <Badge variant="muted" className="shrink-0 tabular-nums">
                    {Math.round(consideration.percent)}%
                  </Badge>
                </li>
              ))}
            </ul>
          </div>
        )}

        {current.regle_droit && (
          <div className="rounded-lg border-l-2 border-primary bg-muted/30 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Règle de droit
            </p>
            <p className="mt-1 text-sm leading-relaxed text-foreground/90">
              {current.regle_droit}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
