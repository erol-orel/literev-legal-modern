import { api } from "@/lib/api-client";
import type { ApiUrls } from "@/lib/context";

/** Exact ProjectRAG status values (see models.ProjectRAG.STATUS_CHOICES). */
export type RagStatus =
  | "in-progress"
  | "questioning_documents"
  | "generating_scores"
  | "generating_summary"
  | "generating_statistics"
  | "tagging_considerations"
  | "completed"
  | "failed";

/** A RAG run is still working until it reaches a terminal state. */
export function isProcessing(status: RagStatus | undefined | null): boolean {
  return Boolean(status && status !== "completed" && status !== "failed");
}

export interface RagReference {
  id: number;
  procedure_type: string;
}

/** key_elements / law_articles rows have arbitrary columns + optional refs. */
export interface RagKeyElement {
  references?: RagReference[];
  /** Canonical statute URL for a law-article row (Fedlex), when resolvable. */
  article_url?: string;
  [key: string]: unknown;
}

export interface RagConsideration {
  text: string;
  frequency: number;
  percent: number;
  procedure_types: string[];
}

export interface RagHistoryEntry {
  id: number;
  query: string;
  status: RagStatus;
  status_display: string;
  valid_answer_count: number;
  num_documents: number;
  created_at: string;
}

export interface CurrentRag {
  id: number;
  query: string;
  status: RagStatus;
  status_display: string;
  summary_text: string;
  considerations: RagConsideration[];
  regle_droit: string;
  key_elements: RagKeyElement[];
  law_articles: RagKeyElement[];
  show_closed_stats: boolean;
  counts: { oui: number; non: number; peut_etre: number; mixte: number };
  percentages: { oui: number; non: number; peut_etre: number; mixte: number };
  has_section_ans: boolean;
  has_confidence_score: boolean;
  valid_answer_count: number;
  num_documents: number;
}

export interface RagContext {
  project: { id: number; name: string; natural_language_query: string };
  current: CurrentRag | null;
  history: RagHistoryEntry[];
  documents_ids: number[];
  number_documents: number;
  refinement: { id: number | null; iteration_id: number | null };
  urls: { back: string; rag_base: string };
}

export interface ProjectRag {
  id: number;
  project: number;
  query: string;
  created_at: string;
  status: RagStatus;
  status_display: string;
  valid_answer_count: number;
  num_documents: number;
}

export interface RagDocumentAnswer {
  id: number;
  project_rag: number;
  citation: string;
  answer: string;
  confidence_score: number | null;
  document: {
    id: number;
    procedure_type: string;
    decision_type: string;
    decision_date: string | null;
    result: string;
    standards: string;
    procedure_year: string | null;
    url_document: string;
  };
}

export function fetchRagContext(
  apiUrls: ApiUrls,
  projectId: string | number,
  ragId?: string | number,
): Promise<RagContext> {
  const suffix = ragId ? `${projectId}/context/${ragId}/` : `${projectId}/context/`;
  return api.get(`${apiUrls.ragContextBase}${suffix}`);
}

export function createRagEntry(
  apiUrls: ApiUrls,
  projectId: string | number,
  body: { query: string; documents_ids: number[] },
): Promise<ProjectRag> {
  return api.post(`${apiUrls.ragCreateBase}${projectId}/`, {
    project_id: Number(projectId),
    query: body.query,
    documents_ids: body.documents_ids,
  });
}

export function fetchRagStatus(
  apiUrls: ApiUrls,
  projectId: string | number,
  ragId: string | number,
): Promise<ProjectRag> {
  return api.get(`${apiUrls.ragStatusBase}${projectId}/${ragId}/`);
}

export function fetchRagDocuments(
  apiUrls: ApiUrls,
  ragId: string | number,
): Promise<RagDocumentAnswer[]> {
  const params = new URLSearchParams({ project_rag: String(ragId) });
  return api.get(`${apiUrls.ragDocumentsBase}?${params.toString()}`);
}

export function deleteRagEntry(
  apiUrls: ApiUrls,
  projectId: string | number,
  ragId: string | number,
): Promise<{ detail: string }> {
  return api.delete(`${apiUrls.ragDeleteBase}${projectId}/${ragId}/`);
}

/**
 * Section-answer parsing (Faits / Subsomption / Conclusion). The `answer` field
 * is a JSON string whose keys are section names; values are strings or string
 * arrays. Preserves the exact alias handling from the legacy page.
 */
const SECTION_KEYS = {
  facts: ["Faits", "Mineure-Faits", "Examen des faits"],
  subsumption: [
    "Subsomption",
    "Mineure-Subsomption",
    "Subsommation",
    "Mineure-Subsommation",
    "Analyse juridique (subsomption)",
  ],
  conclusion: ["Conclusion", "Décision finale"],
} as const;

const INVALID_ANSWER_MARKERS = [
  "No content available",
  "Error generating response",
  "Réponse non disponible",
];

export interface SectionAnswer {
  facts: string;
  subsumption: string;
  conclusion: string;
}

function asText(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join(" ").trim();
  if (value == null) return "";
  return String(value).trim();
}

function pickText(
  source: Record<string, unknown>,
  keys: readonly string[],
): string {
  for (const key of keys) {
    if (source[key] !== undefined) {
      const text = asText(source[key]);
      if (text) return text;
    }
  }
  return "";
}

export function parseSectionAnswers(answerText: string): SectionAnswer | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(answerText);
  } catch {
    return null;
  }
  if (!parsed || typeof parsed !== "object") return null;
  const record = parsed as Record<string, unknown>;

  const hasAny =
    SECTION_KEYS.facts.some((k) => record[k] !== undefined) ||
    SECTION_KEYS.subsumption.some((k) => record[k] !== undefined) ||
    SECTION_KEYS.conclusion.some((k) => record[k] !== undefined);
  if (!hasAny) return null;

  return {
    facts: pickText(record, SECTION_KEYS.facts),
    subsumption: pickText(record, SECTION_KEYS.subsumption),
    conclusion: pickText(record, SECTION_KEYS.conclusion),
  };
}

export function isInvalidAnswer(answer: string): boolean {
  return INVALID_ANSWER_MARKERS.some((marker) => answer.includes(marker));
}
