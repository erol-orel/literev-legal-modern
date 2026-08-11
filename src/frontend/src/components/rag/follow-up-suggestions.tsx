import { CornerDownRight } from "lucide-react";

import type { CurrentRag } from "@/api/rag";

/**
 * Suggested follow-up questions over the *same* document set — the way a jurist
 * actually works a problem: ask, read, then narrow or probe the other side.
 * Picking one pre-fills the composer (the user reviews and asks), reusing the
 * existing "ask across these documents" flow with no backend change.
 *
 * Phrased in French to match the legal content; a mixed closed-question verdict
 * adds a "what distinguishes the two lines" prompt, the most useful next
 * question when the corpus doesn't agree.
 */
export function FollowUpSuggestions({
  current,
  onPick,
}: {
  current: CurrentRag;
  onPick: (question: string) => void;
}) {
  if (!current.query) return null;

  const suggestions = buildSuggestions(current);
  if (suggestions.length === 0) return null;

  return (
    <div className="mt-3 space-y-1.5">
      <p className="flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        <CornerDownRight className="size-3" /> Follow up
      </p>
      <div className="flex flex-wrap gap-1.5">
        {suggestions.map((question) => (
          <button
            key={question}
            type="button"
            onClick={() => onPick(question)}
            className="rounded-full border px-3 py-1 text-xs text-foreground/90 transition-colors hover:border-primary hover:bg-primary/5 hover:text-foreground"
          >
            {question}
          </button>
        ))}
      </div>
    </div>
  );
}

function buildSuggestions(current: CurrentRag): string[] {
  const suggestions = [
    "Quelles sont les conditions à remplir ?",
    "Y a-t-il des exceptions ?",
    "Existe-t-il des décisions en sens contraire ?",
  ];

  // When the corpus is split, the most useful next question is what separates
  // the two lines of decisions.
  const nonZero = (["oui", "non", "peut_etre", "mixte"] as const).filter(
    (key) => current.counts[key] > 0,
  );
  if (current.show_closed_stats && nonZero.length > 1) {
    suggestions.push(
      "Qu'est-ce qui distingue les décisions favorables des défavorables ?",
    );
  }

  suggestions.push("Résume la jurisprudence en trois points.");
  return suggestions;
}
