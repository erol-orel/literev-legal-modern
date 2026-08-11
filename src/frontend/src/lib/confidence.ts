import type { RagDocumentAnswer } from "@/api/rag";

export type ConfidenceVariant = "success" | "warning" | "muted";

/** Faithfulness thresholds shared across the answer + evidence UI. */
export function confidenceVariant(score: number): ConfidenceVariant {
  if (score >= 0.7) return "success";
  if (score >= 0.4) return "warning";
  return "muted";
}

/** Mean faithfulness across the answers that carry a score, or null. */
export function meanConfidence(answers: RagDocumentAnswer[]): number | null {
  const scores = answers
    .map((a) => a.confidence_score)
    .filter((s): s is number => s != null);
  if (scores.length === 0) return null;
  return scores.reduce((sum, s) => sum + s, 0) / scores.length;
}
