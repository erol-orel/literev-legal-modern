import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Check,
  ChevronRight,
  Download,
  FileText,
  FilePlus2,
  HelpCircle,
  Loader2,
  MessagesSquare,
  RotateCcw,
  Repeat,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { PageHeader } from "@/components/common/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { useAppContext } from "@/hooks/use-app-context";
import { useToast } from "@/hooks/use-toast";
import {
  activateTableSelectionIteration,
  askSelectedTableDocuments,
  deleteTableSelectionIteration,
  exportTableSelection,
  fetchTableSelectionState,
  filenameFromDisposition,
  iterateTableSelection,
  resetTableSelection,
  selectionPayloadFrom,
  setAllTableSelection,
  updateTableSelection,
  verdictFromRow,
  type TableSelectionIteration,
  type TableSelectionRow,
  type TableSelectionFilters,
  type Verdict,
} from "@/api/table-selection";
import { ApiError } from "@/lib/api-client";
import { formatDate, formatNumber } from "@/lib/utils";

interface RouteState {
  projectId: string | null;
  refinementId: string | null;
  iterationId: number | null;
  page: number;
  orderBy: string;
}

/** Parse the legacy path scheme the backend still emits and links against. */
function parseRoute(pathname: string): RouteState {
  const detail = pathname.match(
    /^\/tableselect\/(\d+)\/(\d+)\/(\d+)\/page=(\d+)\/order_by=([^/]+)\/?$/,
  );
  if (detail) {
    return {
      projectId: detail[1],
      refinementId: detail[2],
      iterationId: Number(detail[3]),
      page: Number(detail[4]),
      orderBy: decodeURIComponent(detail[5]),
    };
  }

  const base = pathname.match(/^\/tableselect\/(\d+)\/(\d+)\/?$/);
  if (base) {
    return {
      projectId: base[1],
      refinementId: base[2],
      iterationId: null,
      page: 1,
      orderBy: "es_score",
    };
  }

  return {
    projectId: null,
    refinementId: null,
    iterationId: null,
    page: 1,
    orderBy: "es_score",
  };
}

function normalizePath(pathname: string): string {
  if (!pathname) return "/";
  return pathname.endsWith("/") ? pathname : `${pathname}/`;
}

export function TableSelectPage() {
  const { api: apiUrls, urls } = useAppContext();
  const { toast } = useToast();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const route = useMemo(() => parseRoute(location.pathname), [location.pathname]);
  const { projectId, refinementId, iterationId, page, orderBy } = route;

  const [verdicts, setVerdicts] = useState<Record<number, Verdict>>({});
  const [sortSelection, setSortSelection] = useState(orderBy);

  const stateQuery = useQuery({
    queryKey: ["tableselect", projectId, refinementId, iterationId, page, orderBy],
    queryFn: () =>
      fetchTableSelectionState(apiUrls, {
        projectId: projectId as string,
        refinementId: refinementId as string,
        iterationId,
        page,
        orderBy,
      }),
    enabled: Boolean(projectId && refinementId),
    // Poll while the backend recomputes results for a new filter/iteration.
    refetchInterval: (query) =>
      query.state.data?.processing_filters ? 1300 : false,
  });

  const data = stateQuery.data;
  const rows = useMemo(() => data?.table.rows ?? [], [data?.table.rows]);

  // The canonical URL wins: the backend resolves the active iteration/page.
  useEffect(() => {
    if (
      data?.canonical_url &&
      normalizePath(data.canonical_url) !== normalizePath(location.pathname)
    ) {
      navigate(data.canonical_url, { replace: true });
    }
  }, [data?.canonical_url, location.pathname, navigate]);

  // Seed the tri-state control from each freshly loaded page of rows.
  useEffect(() => {
    setVerdicts(
      Object.fromEntries(rows.map((row) => [row.id, verdictFromRow(row)])),
    );
  }, [rows]);

  useEffect(() => {
    if (data?.table.sort_by) setSortSelection(data.table.sort_by);
  }, [data?.table.sort_by]);

  useEffect(() => {
    if (data?.project.name) {
      document.title = `LiteRev Legal | ${data.project.name} Results`;
    }
  }, [data?.project.name]);

  const currentSelection = useMemo(
    () => selectionPayloadFrom(verdicts),
    [verdicts],
  );

  const notifyError = (title: string) => (error: unknown) =>
    toast({
      variant: "destructive",
      title,
      description:
        error instanceof ApiError ? error.messages.join(" ") : "Unexpected error.",
    });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["tableselect"] });

  function buildPath(nextPage: number, nextOrderBy: string): string {
    const base = urls.tableselectBase;
    if (!data?.current_iteration_id) return `${base}${projectId}/${refinementId}/`;
    return `${base}${projectId}/${refinementId}/${data.current_iteration_id}/page=${nextPage}/order_by=${nextOrderBy}/`;
  }

  /** Persist the current page's verdicts before leaving it. */
  async function syncCurrentPage() {
    if (!data?.current_iteration_id) return;
    await updateTableSelection(apiUrls, {
      projectId: projectId as string,
      refinementId: refinementId as string,
      iterationId: data.current_iteration_id,
      selection: currentSelection,
    });
  }

  const navigatePage = useMutation({
    mutationFn: async (args: { page: number; orderBy: string }) => {
      await syncCurrentPage();
      return buildPath(args.page, args.orderBy);
    },
    onSuccess: (path) => navigate(path),
    onError: notifyError("Could not update the page"),
  });

  const checkAll = useMutation({
    // check-all only supports bulk "yes"/"maybe" (no bulk "no").
    mutationFn: (mode: Exclude<Verdict, "no">) =>
      setAllTableSelection(apiUrls, {
        projectId: projectId as string,
        refinementId: refinementId as string,
        iterationId: data?.current_iteration_id ?? null,
        mode,
      }),
    onSuccess: (result) => {
      toast({ variant: "success", title: result.detail || "Selection updated" });
      invalidate();
    },
    onError: notifyError("Could not update the selection"),
  });

  const activate = useMutation({
    mutationFn: (target: number) =>
      activateTableSelectionIteration(apiUrls, {
        projectId: projectId as string,
        refinementId: refinementId as string,
        iterationId: target,
        orderBy: data?.table.sort_by,
      }),
    onSuccess: (result) => navigate(result.url),
    onError: notifyError("Could not open the iteration"),
  });

  const removeIteration = useMutation({
    mutationFn: (target: number) =>
      deleteTableSelectionIteration(apiUrls, {
        projectId: projectId as string,
        refinementId: refinementId as string,
        iterationId: target,
        orderBy: data?.table.sort_by,
      }),
    onSuccess: (result) => {
      toast({ variant: "success", title: result.detail || "Iteration removed" });
      navigate(result.url);
    },
    onError: notifyError("Could not remove the iteration"),
  });

  const iterate = useMutation({
    mutationFn: () =>
      iterateTableSelection(apiUrls, {
        projectId: projectId as string,
        refinementId: refinementId as string,
        iterationId: data?.current_iteration_id ?? null,
        selection: currentSelection,
      }),
    onSuccess: (result) => navigate(result.url),
    onError: notifyError("Could not iterate"),
  });

  const reset = useMutation({
    mutationFn: () =>
      resetTableSelection(apiUrls, {
        projectId: projectId as string,
        refinementId: refinementId as string,
      }),
    onSuccess: (result) => navigate(result.url),
    onError: notifyError("Could not reset iterations"),
  });

  const askSelected = useMutation({
    mutationFn: () =>
      askSelectedTableDocuments(apiUrls, {
        projectId: projectId as string,
        refinementId: refinementId as string,
        iterationId: data?.current_iteration_id ?? null,
        selection: currentSelection,
      }),
    onSuccess: (result) => navigate(result.url),
    onError: notifyError("Could not prepare the questions"),
  });

  const exportCsv = useMutation({
    mutationFn: () =>
      exportTableSelection(apiUrls, {
        projectId: projectId as string,
        refinementId: refinementId as string,
        iterationId: data?.current_iteration_id ?? null,
        selection: currentSelection,
      }),
    onSuccess: ({ blob, filename }) => {
      const objectUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filenameFromDisposition(filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(objectUrl);
    },
    onError: notifyError("Could not export the selection"),
  });

  const busy =
    navigatePage.isPending ||
    checkAll.isPending ||
    activate.isPending ||
    removeIteration.isPending ||
    iterate.isPending ||
    reset.isPending ||
    askSelected.isPending ||
    exportCsv.isPending;

  if (!projectId || !refinementId) {
    return (
      <>
        <PageHeader title="Results table" />
        <Alert variant="destructive">
          <AlertTitle>Invalid link</AlertTitle>
          <AlertDescription>
            This document-selection link is malformed. Open it again from your
            project's refinements.
          </AlertDescription>
        </Alert>
      </>
    );
  }

  if (stateQuery.isLoading) {
    return (
      <>
        <PageHeader title="Results table" />
        <div className="space-y-4">
          <Skeleton className="h-40 w-full" />
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-44 w-full" />
          ))}
        </div>
      </>
    );
  }

  if (stateQuery.isError || !data) {
    return (
      <>
        <PageHeader title="Results table" />
        <Alert variant="destructive">
          <AlertTitle>Could not load the results table</AlertTitle>
          <AlertDescription>
            {stateQuery.error instanceof ApiError
              ? stateQuery.error.messages.join(" ")
              : "Please try again."}
          </AlertDescription>
        </Alert>
      </>
    );
  }

  const { project, counts, table } = data;

  const actionBar = (
    <div className="flex flex-wrap items-center gap-2">
      <Button asChild variant="outline" size="sm">
        <Link to={data.urls.back_to_filter}>
          <ArrowLeft className="size-4" /> Back to filter
        </Link>
      </Button>
      {project.can_iterate && (
        <Button
          variant="secondary"
          size="sm"
          onClick={() => iterate.mutate()}
          disabled={busy}
        >
          {iterate.isPending ? <Spinner className="size-4" /> : <Repeat className="size-4" />}
          Iterate
        </Button>
      )}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => reset.mutate()}
        disabled={busy}
      >
        {reset.isPending ? <Spinner className="size-4" /> : <RotateCcw className="size-4" />}
        Reset
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={() => exportCsv.mutate()}
        disabled={busy}
      >
        {exportCsv.isPending ? <Spinner className="size-4" /> : <Download className="size-4" />}
        Export selected
      </Button>
      <Button size="sm" onClick={() => askSelected.mutate()} disabled={busy}>
        {askSelected.isPending ? (
          <Spinner className="size-4" />
        ) : (
          <MessagesSquare className="size-4" />
        )}
        Ask selected
      </Button>
    </div>
  );

  return (
    <>
      <PageHeader
        title="Results table"
        description="Triage the retrieved decisions, then iterate on the neighbours or ask your selection."
        actions={actionBar}
      />

      {data.processing_filters ? (
        <Card>
          <CardContent className="flex items-center justify-center gap-3 py-16 text-muted-foreground">
            <Loader2 className="size-5 animate-spin text-primary" />
            <span className="text-sm">Processing new results…</span>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
            <ProjectDetails project={project} />
            <SelectionSummary
              counts={counts}
              filters={data.filters}
              busy={busy}
              onCheckAll={(mode) => checkAll.mutate(mode)}
            />
          </div>

          <IterationTrail
            iterations={data.iterations}
            busy={busy}
            onActivate={(id) => activate.mutate(id)}
            onDelete={(id) => removeIteration.mutate(id)}
          />

          <TableToolbar
            sortValue={sortSelection}
            sortOptions={table.sort_options}
            currentPage={table.current_page}
            totalPages={table.total_pages}
            busy={busy}
            onSortChange={setSortSelection}
            onApply={() => navigatePage.mutate({ page: 1, orderBy: sortSelection })}
          />

          <PaginationControls
            currentPage={table.current_page}
            totalPages={table.total_pages}
            busy={busy}
            onNavigate={(nextPage) =>
              navigatePage.mutate({ page: nextPage, orderBy: table.sort_by })
            }
          />

          {rows.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center text-sm text-muted-foreground">
                No documents on this page.
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {rows.map((row) => (
                <DocumentRow
                  key={row.id}
                  row={row}
                  verdict={verdicts[row.id] ?? "maybe"}
                  hasEsScores={table.has_es_scores}
                  hasHdbscanScores={table.has_hdbscan_scores}
                  onVerdict={(value) =>
                    setVerdicts((prev) => ({ ...prev, [row.id]: value }))
                  }
                />
              ))}
            </div>
          )}

          <PaginationControls
            currentPage={table.current_page}
            totalPages={table.total_pages}
            busy={busy}
            onNavigate={(nextPage) =>
              navigatePage.mutate({ page: nextPage, orderBy: table.sort_by })
            }
          />

          <Card>
            <CardContent className="flex items-center justify-between gap-3 py-4">
              <p className="text-sm text-muted-foreground">
                Documents checked:{" "}
                <span className="font-semibold text-foreground">
                  {formatNumber(counts.chosen ?? 0)}
                </span>
              </p>
              {actionBar}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}

function ProjectDetails({
  project,
}: {
  project: {
    name: string;
    creation_date: string;
    query: string;
    range_begin_date: string;
    range_end_date: string;
    processed_documents: number;
  };
}) {
  const rows: [string, React.ReactNode][] = [
    ["Project", project.name],
    ["Created", formatDate(project.creation_date)],
    ["Query", project.query],
    [
      "Date range",
      `${formatDate(project.range_begin_date)} → ${formatDate(project.range_end_date)}`,
    ],
    ["Documents", formatNumber(project.processed_documents)],
  ];

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Details</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="divide-y text-sm">
          {rows.map(([label, value]) => (
            <div key={label} className="grid grid-cols-3 gap-2 py-2">
              <dt className="font-medium text-muted-foreground">{label}</dt>
              <dd className="col-span-2 break-words text-foreground">{value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

function SelectionSummary({
  counts,
  filters,
  busy,
  onCheckAll,
}: {
  counts: { initial?: number; neighbour?: number; chosen?: number };
  filters?: TableSelectionFilters;
  busy: boolean;
  onCheckAll: (mode: Exclude<Verdict, "no">) => void;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Selection</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="grid grid-cols-3 gap-2 text-center">
          <SummaryStat label="Initial" value={counts.initial ?? 0} />
          <SummaryStat label="New neighbours" value={counts.neighbour ?? 0} />
          <SummaryStat label="Checked" value={counts.chosen ?? 0} />
        </div>

        {(filters?.union_sets_html || filters?.excluded_set_html) && (
          <div className="space-y-2 rounded-md border bg-muted/30 p-3 text-xs">
            {filters.union_sets_html && (
              <FilterRow label="Refinement criteria" html={filters.union_sets_html} />
            )}
            {filters.excluded_set_html && (
              <FilterRow label="Excluded set" html={filters.excluded_set_html} />
            )}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onCheckAll("yes")}
            disabled={busy}
          >
            <Check className="size-4 text-success" /> All to Yes
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onCheckAll("maybe")}
            disabled={busy}
          >
            <HelpCircle className="size-4 text-muted-foreground" /> All to Maybe
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function SummaryStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border bg-card p-2">
      <p className="text-lg font-semibold text-foreground">{formatNumber(value)}</p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

function FilterRow({ label, html }: { label: string; html: string }) {
  return (
    <div>
      <p className="font-medium text-muted-foreground">{label}</p>
      {/* Trusted, server-rendered fragment from same-origin Django. */}
      <div
        className="[&_*]:!text-foreground"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}

function IterationTrail({
  iterations,
  busy,
  onActivate,
  onDelete,
}: {
  iterations: TableSelectionIteration[];
  busy: boolean;
  onActivate: (id: number) => void;
  onDelete: (id: number) => void;
}) {
  if (!iterations.length) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {iterations.map((iteration) => {
        const canDelete = !iteration.is_parent && !iteration.is_root;
        return (
          <div key={iteration.id} className="flex items-center gap-1">
            {iteration.is_active ? (
              <Badge variant="default" className="px-3 py-1">
                {iteration.name}
              </Badge>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onActivate(iteration.id)}
                disabled={busy}
              >
                {iteration.name}
              </Button>
            )}
            {canDelete && (
              <Button
                variant="ghost"
                size="icon"
                className="size-7 text-destructive hover:bg-destructive/10 hover:text-destructive"
                onClick={() => onDelete(iteration.id)}
                disabled={busy}
                aria-label={`Delete ${iteration.name}`}
              >
                <X className="size-3.5" />
              </Button>
            )}
            {iteration.is_parent && (
              <ChevronRight className="size-4 text-muted-foreground" />
            )}
          </div>
        );
      })}
    </div>
  );
}

function TableToolbar({
  sortValue,
  sortOptions,
  currentPage,
  totalPages,
  busy,
  onSortChange,
  onApply,
}: {
  sortValue: string;
  sortOptions: { value: string; label: string }[];
  currentPage: number;
  totalPages: number;
  busy: boolean;
  onSortChange: (value: string) => void;
  onApply: () => void;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-muted-foreground">Sort by</span>
        <Select value={sortValue} onValueChange={onSortChange}>
          <SelectTrigger className="w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {sortOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button size="sm" onClick={onApply} disabled={busy}>
          Apply
        </Button>
      </div>
      <p className="text-sm text-muted-foreground">
        Page{" "}
        <span className="font-semibold text-foreground">{currentPage}</span> /{" "}
        {totalPages}
      </p>
    </div>
  );
}

function PaginationControls({
  currentPage,
  totalPages,
  busy,
  onNavigate,
}: {
  currentPage: number;
  totalPages: number;
  busy: boolean;
  onNavigate: (page: number) => void;
}) {
  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between">
      <Button
        variant="outline"
        size="sm"
        onClick={() => onNavigate(currentPage - 1)}
        disabled={busy || currentPage <= 1}
      >
        Previous
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={() => onNavigate(currentPage + 1)}
        disabled={busy || currentPage >= totalPages}
      >
        Next
      </Button>
    </div>
  );
}

const VERDICT_OPTIONS: {
  value: Verdict;
  label: string;
  icon: typeof Check;
  activeClass: string;
}[] = [
  { value: "yes", label: "Yes", icon: Check, activeClass: "bg-success text-white" },
  {
    value: "maybe",
    label: "Maybe",
    icon: HelpCircle,
    activeClass: "bg-secondary text-secondary-foreground",
  },
  { value: "no", label: "No", icon: X, activeClass: "bg-destructive text-white" },
];

function VerdictSelector({
  value,
  documentId,
  onChange,
}: {
  value: Verdict;
  documentId: number;
  onChange: (value: Verdict) => void;
}) {
  return (
    <div
      role="radiogroup"
      aria-label="Document verdict"
      className="grid grid-cols-3 gap-1 rounded-lg border bg-muted/40 p-1 sm:grid-cols-1"
    >
      {VERDICT_OPTIONS.map((option) => {
        const active = value === option.value;
        const Icon = option.icon;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            id={`verdict-${option.value}-${documentId}`}
            onClick={() => onChange(option.value)}
            className={`inline-flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
              active
                ? option.activeClass
                : "text-muted-foreground hover:bg-background hover:text-foreground"
            }`}
          >
            <Icon className="size-4" />
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function DocumentRow({
  row,
  verdict,
  hasEsScores,
  hasHdbscanScores,
  onVerdict,
}: {
  row: TableSelectionRow;
  verdict: Verdict;
  hasEsScores: boolean;
  hasHdbscanScores: boolean;
  onVerdict: (value: Verdict) => void;
}) {
  return (
    <Card>
      <CardContent className="grid gap-4 p-5 sm:grid-cols-[10rem_1fr]">
        <VerdictSelector
          value={verdict}
          documentId={row.id}
          onChange={onVerdict}
        />

        <div className="min-w-0 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              {hasEsScores && row.es_score !== undefined && (
                <Badge variant="secondary">
                  Query relevance {Number(row.es_score).toFixed(2)}
                </Badge>
              )}
              {row.is_initial === false && (
                <Badge variant="warning">
                  <FilePlus2 className="size-3.5" /> New neighbour
                </Badge>
              )}
            </div>
            <Button asChild variant="outline" size="sm">
              <Link to={row.content_url}>
                <FileText className="size-4" />
                {row.procedure_type || "Open document"}
              </Link>
            </Button>
          </div>

          <div className="text-sm text-foreground">
            <span className="font-semibold">{row.decision_type || "—"}</span>
            {row.decision_date ? `, ${formatDate(row.decision_date)}` : ""}
            {"  "}
            <span className="text-muted-foreground">Result:</span>{" "}
            {row.result || "—"}
          </div>

          <div className="text-sm">
            <span className="font-semibold text-muted-foreground">Normes:</span>{" "}
            {row.standards || "—"}
          </div>

          <div className="text-sm">
            <span className="font-semibold text-muted-foreground">Extraits:</span>{" "}
            {/* Trusted, server-rendered excerpt from same-origin Django. */}
            <span
              className="text-foreground/90"
              dangerouslySetInnerHTML={{ __html: `${row.sample_document || ""} …` }}
            />
          </div>

          {hasHdbscanScores && (
            <div className="flex flex-wrap items-center gap-2">
              <span
                className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium text-foreground"
                style={{ backgroundColor: `${row.color || "#adb5bd"}80` }}
              >
                {row.topic}
              </span>
              <Badge variant="muted">
                Topic score {Number(row.hdbscan_score || 0).toFixed(1)}%
              </Badge>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
