import { describe, expect, it } from "vitest";

import type { RagDocumentAnswer } from "@/api/rag";
import { confidenceVariant, meanConfidence } from "@/lib/confidence";

const answer = (confidence_score: number | null): RagDocumentAnswer => ({
  id: 1,
  project_rag: 1,
  citation: "",
  answer: "",
  confidence_score,
  document: {
    id: 1,
    procedure_type: "",
    decision_type: "",
    decision_date: null,
    result: "",
    standards: "",
    procedure_year: null,
    url_document: "",
  },
});

describe("confidenceVariant", () => {
  it("maps >= 0.7 to success", () => {
    expect(confidenceVariant(0.7)).toBe("success");
    expect(confidenceVariant(0.95)).toBe("success");
  });

  it("maps [0.4, 0.7) to warning", () => {
    expect(confidenceVariant(0.4)).toBe("warning");
    expect(confidenceVariant(0.69)).toBe("warning");
  });

  it("maps < 0.4 to muted", () => {
    expect(confidenceVariant(0.39)).toBe("muted");
    expect(confidenceVariant(0)).toBe("muted");
  });
});

describe("meanConfidence", () => {
  it("returns null when no answer carries a score", () => {
    expect(meanConfidence([])).toBeNull();
    expect(meanConfidence([answer(null), answer(null)])).toBeNull();
  });

  it("averages only the scored answers, ignoring nulls", () => {
    expect(meanConfidence([answer(0.5), answer(1), answer(null)])).toBeCloseTo(
      0.75,
    );
  });
});
