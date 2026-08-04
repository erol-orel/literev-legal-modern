import { useMutation } from "@tanstack/react-query";
import {
  CalendarDays,
  Database,
  FileSearch,
  FolderPlus,
  Landmark,
  Sparkles,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { PageHeader } from "@/components/common/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { useAppContext } from "@/hooks/use-app-context";
import {
  convertToBooleanQuery,
  createSearchProject,
  previewSearch,
  type SearchPayload,
  type SearchPreview,
} from "@/api/search";
import { ApiError } from "@/lib/api-client";
import { cn, formatNumber } from "@/lib/utils";

const DEFAULT_SOURCES = [
  { value: "chambre_civile", label: "Chambre Civile" },
  { value: "chambre_penale", label: "Chambre Pénale" },
  { value: "chambre_administrative", label: "Chambre Administrative" },
];

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

interface FormState {
  projectName: string;
  naturalLanguageQuery: string;
  query: string;
  rangeBeginDate: string;
  rangeEndDate: string;
  selectedIndex: string;
}

export function SearchPage() {
  const { api: apiUrls, search } = useAppContext();
  const { toast } = useToast();
  const navigate = useNavigate();

  const sources = useMemo(
    () => (search.sources.length ? search.sources : DEFAULT_SOURCES),
    [search.sources],
  );

  const [form, setForm] = useState<FormState>(() => ({
    projectName: "",
    naturalLanguageQuery: "",
    query: "",
    rangeBeginDate: "2000-01-01",
    rangeEndDate: today(),
    selectedIndex: sources[0]?.value ?? "",
  }));
  const [preview, setPreview] = useState<SearchPreview | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const payload = (): SearchPayload => ({
    project_name: form.projectName,
    selected_indices: form.selectedIndex ? [form.selectedIndex] : [],
    natural_language_query: form.naturalLanguageQuery,
    query: form.query,
    range_begin_date: form.rangeBeginDate,
    range_end_date: form.rangeEndDate,
  });

  const notifyError = (error: unknown) => {
    const messages =
      error instanceof ApiError ? error.messages : ["Something went wrong."];
    toast({
      variant: "destructive",
      title: "Request failed",
      description: messages.join(" "),
    });
  };

  const translate = useMutation({
    mutationFn: () => convertToBooleanQuery(apiUrls, form.naturalLanguageQuery),
    onSuccess: (data) => {
      set("query", data.query);
      toast({ variant: "success", title: "Boolean query generated" });
    },
    onError: notifyError,
  });

  const evaluate = useMutation({
    mutationFn: () => previewSearch(apiUrls, payload()),
    onSuccess: (data) => setPreview(data),
    onError: (error) => {
      setPreview(null);
      notifyError(error);
    },
  });

  const create = useMutation({
    mutationFn: () => createSearchProject(apiUrls, payload()),
    onSuccess: (data) => {
      setConfirmOpen(false);
      toast({
        variant: "success",
        title: "Project created",
        description: `“${data.name}” is now running.`,
      });
      navigate("/running/");
    },
    onError: notifyError,
  });

  const canEvaluate =
    form.projectName.trim() && form.query.trim() && form.selectedIndex;

  const openConfirm = async () => {
    try {
      const data = await previewSearch(apiUrls, payload());
      setPreview(data);
      setConfirmOpen(true);
    } catch (error) {
      notifyError(error);
    }
  };

  return (
    <>
      <PageHeader
        title="New search"
        description="Query French legal decisions, then cluster and interrogate the results."
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <FileSearch className="size-4 text-primary" />
                Define your search
              </CardTitle>
              <CardDescription>
                Name the project, choose a source, and describe what you are
                looking for.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="project-name">Project name</Label>
                <Input
                  id="project-name"
                  placeholder="e.g. Tenant eviction rights 2020–2024"
                  value={form.projectName}
                  onChange={(e) => set("projectName", e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Database className="size-3.5 text-muted-foreground" />
                  Source
                </Label>
                <div className="grid gap-2 sm:grid-cols-3">
                  {sources.map((source) => {
                    const active = form.selectedIndex === source.value;
                    return (
                      <button
                        key={source.value}
                        type="button"
                        onClick={() => set("selectedIndex", source.value)}
                        aria-pressed={active}
                        className={cn(
                          "flex items-center gap-2 rounded-lg border p-3 text-left text-sm transition-colors",
                          active
                            ? "border-primary bg-primary/5 text-foreground ring-1 ring-primary"
                            : "border-input hover:bg-accent",
                        )}
                      >
                        <Landmark
                          className={cn(
                            "size-4 shrink-0",
                            active ? "text-primary" : "text-muted-foreground",
                          )}
                        />
                        <span className="font-medium leading-tight">
                          {source.label}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="nl-query">Natural-language question</Label>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => translate.mutate()}
                    disabled={
                      translate.isPending || !form.naturalLanguageQuery.trim()
                    }
                  >
                    {translate.isPending ? (
                      <Spinner className="size-4" />
                    ) : (
                      <Sparkles className="size-4 text-primary" />
                    )}
                    Generate Boolean query
                  </Button>
                </div>
                <Textarea
                  id="nl-query"
                  rows={3}
                  placeholder="Quels sont les droits du locataire en cas d'expulsion ?"
                  value={form.naturalLanguageQuery}
                  onChange={(e) => set("naturalLanguageQuery", e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Describe your question in plain language and let the assistant
                  draft the Boolean query — or write one directly below.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="boolean-query">Boolean query</Label>
                <Textarea
                  id="boolean-query"
                  rows={3}
                  className="font-mono text-[0.8rem]"
                  placeholder={'"contrat" AND "résiliation" NOT "litige"'}
                  value={form.query}
                  onChange={(e) => set("query", e.target.value)}
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="begin-date" className="flex items-center gap-2">
                    <CalendarDays className="size-3.5 text-muted-foreground" />
                    Decision date from
                  </Label>
                  <Input
                    id="begin-date"
                    type="date"
                    value={form.rangeBeginDate}
                    onChange={(e) => set("rangeBeginDate", e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="end-date" className="flex items-center gap-2">
                    <CalendarDays className="size-3.5 text-muted-foreground" />
                    Decision date to
                  </Label>
                  <Input
                    id="end-date"
                    type="date"
                    value={form.rangeEndDate}
                    onChange={(e) => set("rangeEndDate", e.target.value)}
                  />
                </div>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row">
                <Button
                  variant="outline"
                  className="sm:flex-1"
                  onClick={() => evaluate.mutate()}
                  disabled={!canEvaluate || evaluate.isPending}
                >
                  {evaluate.isPending ? (
                    <Spinner className="size-4" />
                  ) : (
                    <FileSearch className="size-4" />
                  )}
                  Evaluate
                </Button>
                <Button
                  className="sm:flex-1"
                  onClick={openConfirm}
                  disabled={!canEvaluate || create.isPending}
                >
                  <FolderPlus className="size-4" />
                  Create project
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <PreviewPanel preview={evaluate.isPending ? null : preview} loading={evaluate.isPending} />
        </div>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        preview={preview}
        submitting={create.isPending}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => create.mutate()}
      />
    </>
  );
}

function PreviewPanel({
  preview,
  loading,
}: {
  preview: SearchPreview | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center gap-3 py-8 text-sm text-muted-foreground">
          <Spinner className="size-4" /> Evaluating query…
        </CardContent>
      </Card>
    );
  }

  if (!preview) {
    return (
      <Alert variant="info">
        <FileSearch />
        <AlertTitle>Preview</AlertTitle>
        <AlertDescription>
          Run <strong>Evaluate</strong> to estimate how many decisions match
          before creating a project.
        </AlertDescription>
      </Alert>
    );
  }

  const none = preview.total_documents === 0;
  const noCluster = !none && !preview.can_cluster;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardDescription>Estimated matches</CardDescription>
        <CardTitle className="text-3xl">
          {formatNumber(preview.total_documents)}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {none && (
          <Badge variant="destructive">No documents — refine your query</Badge>
        )}
        {noCluster && (
          <Badge variant="warning">
            Below clustering minimum ({preview.clustering_min_documents})
          </Badge>
        )}
        {!none && !noCluster && (
          <Badge variant="success">Ready to cluster</Badge>
        )}
        <dl className="space-y-2 text-sm">
          <Row label="Project" value={preview.project_name} />
          <Row label="Query" value={preview.query} mono />
          <Row
            label="Range"
            value={`${preview.range_begin_date} → ${preview.range_end_date}`}
          />
        </dl>
      </CardContent>
    </Card>
  );
}

function Row({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className={cn("break-words text-foreground", mono && "font-mono text-xs")}>
        {value || "—"}
      </dd>
    </div>
  );
}

function ConfirmDialog({
  open,
  preview,
  submitting,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  preview: SearchPreview | null;
  submitting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const total = preview?.total_documents ?? 0;
  return (
    <Dialog open={open} onOpenChange={(next) => !next && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create this project?</DialogTitle>
          <DialogDescription>
            {total === 0
              ? "No documents match this query. Adjust it before continuing."
              : `About ${formatNumber(total)} decision${total === 1 ? "" : "s"} will be collected, preprocessed and clustered. This runs in the background.`}
          </DialogDescription>
        </DialogHeader>
        {preview && (
          <dl className="space-y-2 rounded-lg border bg-muted/40 p-3 text-sm">
            <Row label="Project" value={preview.project_name} />
            <Row label="Query" value={preview.query} mono />
            <Row
              label="Range"
              value={`${preview.range_begin_date} → ${preview.range_end_date}`}
            />
          </dl>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            disabled={submitting || !preview?.can_continue}
          >
            {submitting && <Spinner className="size-4" />}
            Create &amp; run
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
