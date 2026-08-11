import {
  isInvalidAnswer,
  parseSectionAnswers,
  type RagContext,
  type RagDocumentAnswer,
} from "@/api/rag";
import { formatDate } from "@/lib/utils";

/** A citation string for a single decision's answer (header + sections + quote). */
export function buildAnswerCitation(answer: RagDocumentAnswer): string {
  const { document } = answer;
  const meta = [document.procedure_type, document.decision_type, document.result]
    .filter(Boolean)
    .join(" · ");
  const header = [
    meta,
    document.decision_date ? formatDate(document.decision_date) : "",
  ]
    .filter(Boolean)
    .join(" · ");

  const section = parseSectionAnswers(answer.answer);
  const body = section
    ? (
        [
          ["En fait", section.facts],
          ["Subsomption", section.subsumption],
          ["Conclusion", section.conclusion],
        ] as const
      )
        .filter(([, text]) => text)
        .map(([label, text]) => `${label} : ${text}`)
        .join("\n")
    : answer.answer;

  return [header, body, answer.citation ? `« ${answer.citation} »` : ""]
    .filter(Boolean)
    .join("\n\n");
}

/** The full report as plain text: question, answer, rule of law, and each cited decision. */
export function buildReportText(
  context: RagContext,
  answers: RagDocumentAnswer[],
): string {
  const current = context.current;
  const question =
    context.project.natural_language_query || current?.query || "";
  const parts: string[] = [];

  if (question) parts.push(`Question : ${question}`);
  if (current?.summary_text) parts.push(`Réponse\n${current.summary_text}`);
  if (current?.regle_droit) parts.push(`Règle de droit\n${current.regle_droit}`);

  const valid = answers.filter((a) => !isInvalidAnswer(a.answer));
  if (valid.length > 0) {
    parts.push(
      "Décisions citées\n" +
        valid
          .map((a, index) => `[${index + 1}] ${buildAnswerCitation(a)}`)
          .join("\n\n"),
    );
  }

  return parts.join("\n\n———\n\n");
}
