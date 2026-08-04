import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  FileText,
  Layers,
  MessagesSquare,
  Sparkles,
  Target,
} from "lucide-react";
import { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { BokehPlot } from "@/components/common/bokeh-plot";
import { PageHeader } from "@/components/common/page-header";
import { ProgressDisplay } from "@/components/common/progress-display";
import { RefinementBuilder } from "@/components/project/refinement-builder";
import { RefinementList } from "@/components/project/refinement-list";
import { Stat } from "@/components/common/stat";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useAppContext } from "@/hooks/use-app-context";
import { useToast } from "@/hooks/use-toast";
import {
  askTopDocuments,
  fetchProjectOverview,
  generateProjectClusterSummary,
  isOverviewRedirect,
  type ClusterSummaryItem,
  type ProjectOverview,
} from "@/api/project-overview";
import { ApiError } from "@/lib/api-client";
import { formatDate, formatNumber } from "@/lib/utils";

export function ProjectPage() {
  const { projectId = "" } = useParams();
  const { api: apiUrls } = useAppContext();
  const { toast } = useToast();
  const navigate = useNavigate();

  const overview = useQuery({
    queryKey: ["overview", projectId],
    queryFn: () => fetchProjectOverview(apiUrls, projectId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && !isOverviewRedirect(data) && data.project.is_finish) {
        return false;
      }
      return 8_000;
    },
  });

  const redirect =
    overview.data && isOverviewRedirect(overview.data) ? overview.data : null;

  useEffect(() => {
    if (redirect) navigate("/running/");
  }, [redirect, navigate]);

  if (overview.isLoading) {
    return <ProjectSkeleton />;
  }

  if (overview.isError || !overview.data || redirect) {
    return (
      <>
        <PageHeader title="Project" />
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            {redirect
              ? "This project is still collecting documents…"
              : "This project could not be loaded."}
          </CardContent>
        </Card>
      </>
    );
  }

  const data = overview.data as ProjectOverview;
  const { project } = data;

  return (
    <>
      <PageHeader
        breadcrumb={
          <Button asChild variant="ghost" size="sm" className="-ml-2 h-7">
            <Link to="/historicalpage/">
              <ArrowLeft className="size-4" /> Back to history
            </Link>
          </Button>
        }
        title={project.name}
        description={project.natural_language_query || project.query}
        actions={
          <div className="flex items-center gap-2">
            <Badge variant={project.is_finish ? "success" : "secondary"}>
              {project.step_label}
            </Badge>
            <AskTopDocsButton projectId={projectId} />
          </div>
        }
      />

      {!project.is_finish && (
        <Card className="mb-6">
          <CardContent className="py-4">
            <ProgressDisplay progress={project.progress} />
          </CardContent>
        </Card>
      )}

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Documents"
          value={formatNumber(project.total_documents)}
          icon={FileText}
        />
        <Stat
          label="Processed"
          value={formatNumber(project.processed_documents)}
          icon={Target}
        />
        <Stat
          label="Clusters"
          value={data.no_clusters ? "—" : formatNumber(data.cluster_summaries.length)}
          icon={Layers}
        />
        <Stat
          label="Date range"
          value={`${formatDate(project.range_begin_date)}`}
          hint={`to ${formatDate(project.range_end_date)}`}
        />
      </div>

      {data.plot && (
        <Card className="mb-6">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Layers className="size-4 text-primary" /> Cluster map
            </CardTitle>
            <CardDescription>
              Topical landscape of the retrieved decisions.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <BokehPlot plot={data.plot} />
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-foreground">Clusters</h2>
          {data.no_clusters || data.cluster_summaries.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-sm text-muted-foreground">
                This project has no clusters.
              </CardContent>
            </Card>
          ) : (
            data.cluster_summaries.map((cluster) => (
              <ClusterCard
                key={cluster.cluster_id}
                projectId={projectId}
                cluster={cluster}
              />
            ))
          )}
        </section>

        <aside className="space-y-6">
          <RefinementBuilder
            projectId={projectId}
            filterTypes={data.filters.types}
            limit={data.filters.refinement_limit}
            count={data.filters.refinement_count}
          />
          <RefinementList
            projectId={projectId}
            refinements={data.refinements}
          />
        </aside>
      </div>
    </>
  );

  function AskTopDocsButton({ projectId }: { projectId: string }) {
    const ask = useMutation({
      mutationFn: () => askTopDocuments(apiUrls, projectId),
      onSuccess: (result) => {
        toast({ variant: "success", title: "Top documents prepared" });
        navigate(result.urls.rag.replace(/^\/rag/, "/rag"));
      },
      onError: (error) =>
        toast({
          variant: "destructive",
          title: "Could not prepare documents",
          description:
            error instanceof ApiError ? error.messages.join(" ") : "Error.",
        }),
    });

    if (!project.can_ask_top_docs) return null;
    return (
      <Button onClick={() => ask.mutate()} disabled={ask.isPending}>
        {ask.isPending ? (
          <Spinner className="size-4" />
        ) : (
          <MessagesSquare className="size-4" />
        )}
        Ask top documents
      </Button>
    );
  }
}

function ClusterCard({
  projectId,
  cluster,
}: {
  projectId: string;
  cluster: ClusterSummaryItem;
}) {
  const { api: apiUrls } = useAppContext();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const summarize = useMutation({
    mutationFn: () =>
      generateProjectClusterSummary(apiUrls, projectId, cluster.cluster_id),
    onSuccess: (result) => {
      queryClient.setQueryData<ProjectOverview>(
        ["overview", projectId],
        (prev) =>
          prev
            ? {
                ...prev,
                cluster_summaries: prev.cluster_summaries.map((c) =>
                  c.cluster_id === cluster.cluster_id ? result.cluster : c,
                ),
              }
            : prev,
      );
      toast({ variant: "success", title: "Summary generated" });
    },
    onError: (error) =>
      toast({
        variant: "destructive",
        title: "Summary unavailable",
        description:
          error instanceof ApiError ? error.messages.join(" ") : "Error.",
      }),
  });

  const rep = cluster.representative_document;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start gap-3">
          <span
            className="mt-1 size-3 shrink-0 rounded-full"
            style={{ backgroundColor: cluster.topic_color || "hsl(var(--muted-foreground))" }}
            aria-hidden="true"
          />
          <div className="min-w-0 flex-1">
            <CardTitle className="text-sm font-semibold leading-snug">
              {cluster.topic_label || "Cluster"}
            </CardTitle>
            <CardDescription className="mt-1">
              {formatNumber(cluster.total_documents)} documents
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {cluster.summary_text ? (
          <p className="text-sm leading-relaxed text-foreground/90">
            {cluster.summary_text}
          </p>
        ) : (
          <Button
            variant="outline"
            size="sm"
            onClick={() => summarize.mutate()}
            disabled={summarize.isPending}
          >
            {summarize.isPending ? (
              <Spinner className="size-4" />
            ) : (
              <Sparkles className="size-4 text-primary" />
            )}
            Generate summary
          </Button>
        )}

        {rep && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Link
                to={`/contentdocument/${rep.document_id}/`}
                className="flex items-center gap-2 rounded-md border bg-muted/40 p-2 text-xs text-muted-foreground transition-colors hover:bg-accent"
              >
                <FileText className="size-3.5 shrink-0" />
                <span className="truncate">
                  {[rep.procedure_type, rep.decision_type, rep.result]
                    .filter(Boolean)
                    .join(" · ") || "Representative document"}
                </span>
              </Link>
            </TooltipTrigger>
            <TooltipContent>Open representative document</TooltipContent>
          </Tooltip>
        )}
      </CardContent>
    </Card>
  );
}

function ProjectSkeleton() {
  return (
    <>
      <Skeleton className="mb-6 h-9 w-72" />
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
      <Skeleton className="mb-6 h-80 w-full" />
      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    </>
  );
}
