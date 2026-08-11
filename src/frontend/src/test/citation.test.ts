import { describe, expect, it } from "vitest";

import type { RagContext, RagDocumentAnswer } from "@/api/rag";
import { buildAnswerCitation, buildReportText } from "@/lib/citation";

const makeAnswer = (over: Partial<RagDocumentAnswer> = {}): RagDocumentAnswer => ({
  id: 1,
  project_rag: 1,
  citation: "Le bail peut être résilié.",
  answer: JSON.stringify({
    Faits: "Le locataire conteste.",
    Subsomption: "Art. 271 CO s'applique.",
    Conclusion: "Résiliation valable.",
  }),
  confidence_score: 0.82,
  document: {
    id: 7,
    procedure_type: "Bail",
    decision_type: "Arrêt",
    decision_date: "2023-05-12",
    result: "Admis",
    standards: "",
    language: "fr",
    procedure_year: "2023",
    url_document: "https://example.test/doc/7",
    ...over.document,
  },
  ...over,
});

describe("buildAnswerCitation", () => {
  it("renders header, labelled sections and the verbatim quote", () => {
    const text = buildAnswerCitation(makeAnswer());
    expect(text).toContain("Bail · Arrêt · Admis");
    expect(text).toContain("12 May 2023");
    expect(text).toContain("En fait : Le locataire conteste.");
    expect(text).toContain("Subsomption : Art. 271 CO s'applique.");
    expect(text).toContain("Conclusion : Résiliation valable.");
    expect(text).toContain("« Le bail peut être résilié. »");
  });

  it("falls back to the raw answer for non-section text", () => {
    const text = buildAnswerCitation(
      makeAnswer({ answer: "Plain narrative answer.", citation: "" }),
    );
    expect(text).toContain("Plain narrative answer.");
  });

  it("omits an empty section without leaving a dangling label", () => {
    const text = buildAnswerCitation(
      makeAnswer({
        answer: JSON.stringify({ Faits: "Only facts here." }),
      }),
    );
    expect(text).toContain("En fait : Only facts here.");
    expect(text).not.toContain("Subsomption :");
    expect(text).not.toContain("Conclusion :");
  });
});

describe("buildReportText", () => {
  const context: RagContext = {
    project: {
      id: 1,
      name: "Baux",
      natural_language_query: "Le bailleur peut-il résilier ?",
    },
    current: {
      id: 1,
      query: "resiliation",
      status: "completed",
      status_display: "Completed",
      summary_text: "Dans la majorité des cas la résiliation est admise.",
      considerations: [],
      regle_droit: "Art. 271 CO.",
      key_elements: [],
      law_articles: [],
      show_closed_stats: true,
      counts: { oui: 3, non: 1, peut_etre: 0, mixte: 0 },
      percentages: { oui: 75, non: 25, peut_etre: 0, mixte: 0 },
      has_section_ans: true,
      has_confidence_score: true,
      valid_answer_count: 4,
      num_documents: 4,
    },
    history: [],
    documents_ids: [7],
    number_documents: 1,
    refinement: { id: null, iteration_id: null },
    urls: { back: "", rag_base: "" },
  };

  it("assembles question, answer, rule of law and cited decisions", () => {
    const text = buildReportText(context, [makeAnswer()]);
    expect(text).toContain("Question : Le bailleur peut-il résilier ?");
    expect(text).toContain(
      "Réponse\nDans la majorité des cas la résiliation est admise.",
    );
    expect(text).toContain("Règle de droit\nArt. 271 CO.");
    expect(text).toContain("Décisions citées");
    expect(text).toContain("[1] Bail · Arrêt · Admis");
  });

  it("drops invalid answers from the cited decisions", () => {
    const invalid = makeAnswer({ id: 2, answer: "No content available" });
    const text = buildReportText(context, [invalid]);
    expect(text).not.toContain("Décisions citées");
  });
});
