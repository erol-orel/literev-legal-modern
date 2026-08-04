import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  ArrowLeft,
  ExternalLink,
  Loader2,
  MessagesSquare,
  Pencil,
  RotateCcw,
  Send,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { PageHeader } from "@/components/common/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAppContext } from "@/hooks/use-app-context";
import { useToast } from "@/hooks/use-toast";
import {
  createRagEntry,
  deleteRagEntry,
  fetchRagContext,
  fetchRagDocuments,
  fetchRagStatus,
  isInvalidAnswer,
  isProcessing,
  parseSectionAnswers,
  type RagContext,
  type RagDocumentAnswer,
  type RagHistoryEntry,
  type RagKeyElement,
} from "@/api/rag";
import { ApiError } from "@/lib/api-client";
import { cn, formatDate } from "@/lib/utils";

type SortKey = "date_desc" | "date_asc" | "confidence";

export function RagPage() {
  const { projectId = "", ragId } = useParams();
  const { api: apiUrls } = useAppContext();
  const { toast } = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [query, setQuery] = useState("");
  const [composerOpen, setComposerOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<RagHistoryEntry | null>(null);

  const context = useQuery({
    queryKey: ["rag-context", projectId, ragId ?? null],
    queryFn: () => fetchRagContext(apiUrls, projectId, ragId),
  });

  // Seed the question box from the project's natural-language query.
  useEffect(() => {
    if (context.data?.project.natural_language_query && !ragId) {
      setQuery(context.data.project.natural_language_query);
    }
  }, [context.data, ragId]);

  const status = useQuery({
    queryKey: ["rag-status", projectId, ragId],
    queryFn: () => fetchRagStatus(apiUrls, projectId, ragId!),
    enabled: Boolean(ragId),
    refetchInterval: (query) =>
      isProcessing(query.state.data?.status) ? 1200 : false,
  });

  const answersEnabled = status.data?.status === "completed";
  const answers = useQuery({
    queryKey: ["rag-answers", ragId],
    queryFn: () => fetchRagDocuments(apiUrls, ragId!),
    enabled: Boolean(ragId) && answersEnabled,
  });

  const notifyError = (error: unknown) =>
    toast({
      variant: "destructive",
      title: "Request failed",
      description:
        error instanceof ApiError ? error.messages.join(" ") : "Unexpected error.",
    });

  const ask = useMutation({
    mutationFn: (documentsIds: number[]) =>
      createRagEntry(apiUrls, projectId, {
        query: query.trim().toLowerCase(),
        documents_ids: documentsIds,
      }),
    onSuccess: (rag) => {
      setComposerOpen(false);
      navigate(`/rag/${projectId}/${rag.id}/`);
    },
    onError: notifyError,
  });

  const remove = useMutation({
    mutationFn: (id: number) => deleteRagEntry(apiUrls, projectId, id),
    onSuccess: (_data, id) => {
      toast({ variant: "success", title: "Question removed" });
      setPendingDelete(null);
      queryClient.invalidateQueries({ queryKey: ["rag-context", projectId] });
      if (String(id) === ragId) navigate(`/rag/${projectId}/`);
    },
    onError: notifyError,
  });

  if (context.isLoading) return <RagSkeleton />;

  if (context.isError || !context.data) {
    return (
      <>
        <PageHeader title="Ask the corpus" />
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            This workspace could not be loaded.
          </CardContent>
        </Card>
      </>
    );
  }

  const data = context.data;
  const current = status.data ?? data.current;
  const processing = isProcessing(current?.status);
  const failed = current?.status === "failed";
  const completed = current?.status === "completed";
  const viewingResult = Boolean(ragId && current);

  const canAsk =
    !ask.isPending && Boolean(query.trim()) && data.number_documents > 0;
  const submit = () => canAsk && ask.mutate(data.documents_ids);

  const composer = (
    <div className="space-y-3">
      <Textarea
        rows={viewingResult ? 2 : 3}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit();
        }}
        placeholder="e.g. Le bailleur peut-il résilier le bail de manière anticipée ?"
        autoFocus={viewingResult}
      />
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">
          {data.number_documents === 0
            ? "No documents selected — select documents first."
            : `Runs across ${data.number_documents} document${data.number_documents === 1 ? "" : "s"}. ⌘/Ctrl + Enter to ask.`}
        </p>
        <Button onClick={submit} disabled={!canAsk}>
          {ask.isPending ? (
            <Spinner className="size-4" />
          ) : (
            <Send className="size-4" />
          )}
          Ask
        </Button>
      </div>
    </div>
  );

  return (
    <>
      <PageHeader
        breadcrumb={
          <Button asChild variant="ghost" size="sm" className="-ml-2 h-7">
            <Link to={`/project/${projectId}/`}>
              <ArrowLeft className="size-4" /> Back to project
            </Link>
          </Button>
        }
        title="Ask the corpus"
        description={`${data.number_documents} selected document${data.number_documents === 1 ? "" : "s"} · ${data.project.name}`}
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
        <div className="space-y-6">
          {/*
            Results-first layout: once a question exists we collapse the
            composer into a compact bar showing the current question, so the
            summary and per-document answers are the focal point. The full
            composer only leads on the fresh (no-question) view.
          */}
          {viewingResult ? (
            <Card>
              <CardContent className="py-4">
                {composerOpen ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-medium text-foreground">
                        Ask a new question
                      </p>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7"
                        onClick={() => setComposerOpen(false)}
                      >
                        Cancel
                      </Button>
                    </div>
                    {composer}
                  </div>
                ) : (
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        Question
                      </p>
                      <p className="mt-0.5 text-sm font-medium text-foreground">
                        {current?.query || "—"}
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="shrink-0"
                      onClick={() => {
                        setQuery("");
                        setComposerOpen(true);
                      }}
                    >
                      <Pencil className="size-3.5" /> New question
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Your question</CardTitle>
                <CardDescription>
                  Ask an open or closed-ended question. Answers cite the source
                  decisions.
                </CardDescription>
              </CardHeader>
              <CardContent>{composer}</CardContent>
            </Card>
          )}

          {viewingResult && processing && (
            <AnalyzingState
              statusDisplay={current!.status_display}
              numDocuments={data.number_documents}
            />
          )}

          {viewingResult && failed && (
            <FailedState
              onRetry={() => {
                setQuery(current!.query);
                setComposerOpen(true);
              }}
            />
          )}

          {viewingResult && completed && (
            <>
              <SummaryCard context={data} />
              <AnswersSection
                answers={answers.data ?? []}
                loading={answers.isLoading}
                hasConfidence={data.current?.has_confidence_score ?? false}
              />
            </>
          )}

          {!ragId && (
            <EmptyState
              icon={MessagesSquare}
              title="Ask your first question"
              description="The general summary and per-document answers will appear here as soon as your question is analyzed."
            />
          )}
        </div>

        <aside>
          <HistoryList
            projectId={projectId}
            currentRagId={ragId}
            history={data.history}
            onDelete={setPendingDelete}
          />
        </aside>
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Remove this question?"
        description={pendingDelete ? `“${pendingDelete.query}” will be removed.` : ""}
        confirmLabel="Remove"
        destructive
        loading={remove.isPending}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => pendingDelete && remove.mutate(pendingDelete.id)}
      />
    </>
  );
}

function AnalyzingState({
  statusDisplay,
  numDocuments,
}: {
  statusDisplay: string;
  numDocuments: number;
}) {
  return (
    <div className="space-y-3">
      <Card className="border-primary/30 bg-primary/5">
        <CardContent className="flex items-center gap-3 py-4">
          <Loader2 className="size-5 shrink-0 animate-spin text-primary" />
          <div>
            <p className="text-sm font-medium text-foreground">
              Analyzing {numDocuments} document{numDocuments === 1 ? "" : "s"}…
            </p>
            <p className="text-xs text-muted-foreground">
              {statusDisplay} — the general summary and per-document answers
              will appear here automatically.
            </p>
          </div>
        </CardContent>
      </Card>
      {/* Placeholders that foreshadow the summary + answers to come. */}
      <Skeleton className="h-40 w-full" />
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-32 w-full" />
      ))}
    </div>
  );
}

function FailedState({ onRetry }: { onRetry: () => void }) {
  return (
    <Card className="border-destructive/40">
      <CardContent className="flex items-center justify-between gap-3 py-4">
        <div className="flex items-center gap-3">
          <span className="size-2.5 shrink-0 rounded-full bg-destructive" />
          <div>
            <p className="text-sm font-medium text-foreground">
              This run failed
            </p>
            <p className="text-xs text-destructive">
              No answers were generated. Try asking again.
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCcw className="size-3.5" /> Retry
        </Button>
      </CardContent>
    </Card>
  );
}

function SummaryCard({ context }: { context: RagContext }) {
  const current = context.current;
  if (!current) return null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Summary</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {current.summary_text && (
          <p className="text-sm leading-relaxed text-foreground/90">
            {current.summary_text}
          </p>
        )}

        {current.show_closed_stats && (
          <div className="space-y-2">
            {(["oui", "non", "peut_etre", "mixte"] as const).map((key) => (
              <div key={key} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="capitalize text-muted-foreground">
                    {key.replace("_", " ")}
                  </span>
                  <span className="font-medium text-foreground">
                    {current.counts[key]} ({current.percentages[key]}%)
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-secondary">
                  <div
                    className="h-full bg-primary"
                    style={{ width: `${current.percentages[key]}%` }}
                  />
                </div>
              </div>
            ))}
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
                  <span className="text-foreground/90">{consideration.text}</span>
                  <Badge variant="muted" className="shrink-0">
                    {Math.round(consideration.percent)}%
                  </Badge>
                </li>
              ))}
            </ul>
          </div>
        )}

        {current.regle_droit && (
          <div className="rounded-lg border bg-muted/30 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Règle de droit
            </p>
            <p className="mt-1 text-sm text-foreground/90">{current.regle_droit}</p>
          </div>
        )}

        {current.has_section_ans &&
          current.summary_text &&
          current.key_elements.length > 0 && (
            <RagFactsTable
              title="Éléments clés"
              rows={current.key_elements}
            />
          )}

        {current.law_articles.length > 0 && (
          <RagFactsTable title="Articles de loi" rows={current.law_articles} />
        )}
      </CardContent>
    </Card>
  );
}

/** Prettify an arbitrary payload key into a table header ("law_article" → "Law article"). */
function prettyColumn(key: string): string {
  return key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

function formatCell(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join(", ");
  if (value == null) return "";
  return String(value);
}

/**
 * Renders the RAG "éléments clés" / "articles de loi" tables. Rows are
 * arbitrary column maps (columns taken from the first row) with an optional
 * `references` list rendered as links into the source documents — mirroring the
 * legacy KeyElementsTable / LawArticlesTable.
 */
function RagFactsTable({
  title,
  rows,
}: {
  title: string;
  rows: RagKeyElement[];
}) {
  if (rows.length === 0) return null;
  // `article_url` is metadata for linking the `article` cell, not its own column.
  const columns = Object.keys(rows[0]).filter((col) => col !== "article_url");

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                >
                  {col === "references" ? "Références" : prettyColumn(col)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index} className="border-t align-top">
                {columns.map((col) => (
                  <td key={col} className="px-3 py-2 text-foreground/90">
                    {col === "references" ? (
                      <div className="flex flex-wrap gap-1">
                        {(row.references ?? []).map((ref) => (
                          <Button
                            key={`${ref.id}-${ref.procedure_type}`}
                            asChild
                            variant="secondary"
                            size="sm"
                            className="h-6 px-2 text-xs"
                          >
                            <Link to={`/contentdocument/${ref.id}/`}>
                              {ref.procedure_type}
                            </Link>
                          </Button>
                        ))}
                      </div>
                    ) : col === "article" &&
                      typeof row.article_url === "string" ? (
                      <a
                        href={row.article_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 font-medium text-primary underline-offset-2 hover:underline"
                        title="Ouvrir le texte de loi sur Fedlex"
                      >
                        {formatCell(row[col])}
                        <ExternalLink className="size-3 shrink-0" />
                      </a>
                    ) : (
                      formatCell(row[col])
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AnswersSection({
  answers,
  loading,
  hasConfidence,
}: {
  answers: RagDocumentAnswer[];
  loading: boolean;
  hasConfidence: boolean;
}) {
  const [sort, setSort] = useState<SortKey>("date_desc");

  const visible = useMemo(() => {
    const filtered = answers.filter((a) => !isInvalidAnswer(a.answer));
    const sorted = [...filtered];
    sorted.sort((a, b) => {
      if (sort === "confidence") {
        return (b.confidence_score ?? 0) - (a.confidence_score ?? 0);
      }
      const da = a.document.decision_date ?? "";
      const db = b.document.decision_date ?? "";
      return sort === "date_asc" ? da.localeCompare(db) : db.localeCompare(da);
    });
    return sorted;
  }, [answers, sort]);

  if (loading) {
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-32 w-full" />
        ))}
      </div>
    );
  }

  if (visible.length === 0) {
    return (
      <EmptyState
        icon={MessagesSquare}
        title="No answers"
        description="No valid answers were produced for the selected documents."
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">
          Answers <span className="text-muted-foreground">({visible.length})</span>
        </h2>
        <Select value={sort} onValueChange={(v) => setSort(v as SortKey)}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="date_desc">Newest first</SelectItem>
            <SelectItem value="date_asc">Oldest first</SelectItem>
            {hasConfidence && (
              <SelectItem value="confidence">Highest confidence</SelectItem>
            )}
          </SelectContent>
        </Select>
      </div>
      {visible.map((answer) => (
        <AnswerCard key={answer.id} answer={answer} />
      ))}
    </div>
  );
}

function AnswerCard({ answer }: { answer: RagDocumentAnswer }) {
  const section = parseSectionAnswers(answer.answer);
  const { document } = answer;

  const meta = [document.procedure_type, document.decision_type, document.result]
    .filter(Boolean)
    .join(" · ");

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{document.procedure_type || "Decision"}</Badge>
            {document.decision_date && (
              <span className="text-xs text-muted-foreground">
                {formatDate(document.decision_date)}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {answer.confidence_score != null && (
              <Badge
                variant={
                  answer.confidence_score >= 0.7
                    ? "success"
                    : answer.confidence_score >= 0.4
                      ? "warning"
                      : "muted"
                }
              >
                {Math.round(answer.confidence_score * 100)}% confidence
              </Badge>
            )}
            {document.url_document && (
              <Button asChild variant="ghost" size="sm">
                <a
                  href={document.url_document}
                  target="_blank"
                  rel="noreferrer"
                >
                  Source <ExternalLink className="size-3.5" />
                </a>
              </Button>
            )}
          </div>
        </div>
        {meta && <CardDescription>{meta}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-3">
        {section ? (
          <div className="space-y-3">
            <Section label="En fait" text={section.facts} />
            <Section label="Subsomption" text={section.subsumption} />
            <Section label="Conclusion" text={section.conclusion} />
          </div>
        ) : (
          <p className="text-sm leading-relaxed text-foreground/90">
            {answer.answer}
          </p>
        )}
        {answer.citation && (
          <blockquote className="border-l-2 border-primary/40 pl-3 text-sm italic text-muted-foreground">
            {answer.citation}
          </blockquote>
        )}
      </CardContent>
    </Card>
  );
}

function Section({ label, text }: { label: string; text: string }) {
  if (!text) return null;
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-primary">
        {label}
      </p>
      <p className="mt-0.5 text-sm leading-relaxed text-foreground/90">{text}</p>
    </div>
  );
}

function HistoryList({
  projectId,
  currentRagId,
  history,
  onDelete,
}: {
  projectId: string;
  currentRagId: string | undefined;
  history: RagHistoryEntry[];
  onDelete: (entry: RagHistoryEntry) => void;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Previous questions</CardTitle>
      </CardHeader>
      <CardContent>
        {history.length === 0 ? (
          <p className="py-2 text-sm text-muted-foreground">
            No previous questions.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {history.map((entry) => {
              const active = String(entry.id) === currentRagId;
              return (
                <li
                  key={entry.id}
                  className={cn(
                    "group flex items-start gap-1 rounded-lg border p-2 transition-colors",
                    active ? "border-primary bg-primary/5" : "hover:bg-accent",
                  )}
                >
                  <Link
                    to={`/rag/${projectId}/${entry.id}/`}
                    className="min-w-0 flex-1"
                  >
                    <p className="truncate text-sm font-medium text-foreground">
                      {entry.query}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {entry.status_display} · {formatDate(entry.created_at)}
                    </p>
                  </Link>
                  <button
                    type="button"
                    onClick={() => onDelete(entry)}
                    aria-label={`Remove ${entry.query}`}
                    className="rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function RagSkeleton() {
  return (
    <>
      <Skeleton className="mb-6 h-9 w-64" />
      <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
        <div className="space-y-6">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    </>
  );
}
