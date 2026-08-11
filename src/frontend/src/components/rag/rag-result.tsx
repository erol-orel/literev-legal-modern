import type { RagContext, RagDocumentAnswer } from "@/api/rag";
import { AnswerVerdict } from "@/components/rag/answer-verdict";
import { ReportPanel } from "@/components/rag/report-panel";
import { SourceList } from "@/components/rag/source-list";

/**
 * Answer-first RAG result: the direct answer (general summary + verdict) leads,
 * the extractable report follows, and the cited decisions form the evidence
 * rail beneath — the reading order a jurist actually works in.
 */
export function RagResult({
  context,
  answers,
  answersLoading,
}: {
  context: RagContext;
  answers: RagDocumentAnswer[];
  answersLoading: boolean;
}) {
  const hasConfidence = context.current?.has_confidence_score ?? false;

  return (
    <div className="space-y-6">
      <AnswerVerdict context={context} answers={answers} />
      <ReportPanel context={context} answers={answers} />
      <SourceList
        answers={answers}
        loading={answersLoading}
        hasConfidence={hasConfidence}
      />
    </div>
  );
}
