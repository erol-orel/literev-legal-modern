import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderOpen, Inbox, RotateCcw, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { PageHeader } from "@/components/common/page-header";
import { ProgressDisplay } from "@/components/common/progress-display";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useAppContext } from "@/hooks/use-app-context";
import { useToast } from "@/hooks/use-toast";
import {
  deleteProject,
  fetchRunningProjects,
  restartRunningProject,
  type ProjectListItem,
} from "@/api/projects";
import { ApiError } from "@/lib/api-client";
import { formatNumber } from "@/lib/utils";

export function RunningPage() {
  const { api: apiUrls } = useAppContext();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [pendingDelete, setPendingDelete] = useState<ProjectListItem | null>(null);

  const running = useQuery({
    queryKey: ["running"],
    queryFn: () => fetchRunningProjects(apiUrls),
    refetchInterval: 10_000,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["running"] });

  const notifyError = (error: unknown) =>
    toast({
      variant: "destructive",
      title: "Action failed",
      description:
        error instanceof ApiError ? error.messages.join(" ") : "Unexpected error.",
    });

  const restart = useMutation({
    mutationFn: (id: number) => restartRunningProject(apiUrls, id),
    onSuccess: () => {
      toast({ variant: "success", title: "Restart requested" });
      invalidate();
    },
    onError: notifyError,
  });

  const remove = useMutation({
    mutationFn: (id: number) => deleteProject(apiUrls, id),
    onSuccess: () => {
      toast({ variant: "success", title: "Project deleted" });
      setPendingDelete(null);
      invalidate();
    },
    onError: notifyError,
  });

  const projects = running.data?.projects ?? [];

  return (
    <>
      <PageHeader
        title="Running projects"
        description="Live status of collection, clustering and question-answering jobs. Refreshes automatically."
      />

      {running.isLoading ? (
        <div className="space-y-4">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      ) : projects.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Nothing running"
          description="Start a new search to launch an analysis. Running jobs will appear here."
          action={
            <Button asChild>
              <Link to="/search/">New search</Link>
            </Button>
          }
        />
      ) : (
        <div className="space-y-4">
          {projects.map((project) => (
            <Card key={project.id}>
              <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
                <div className="min-w-0 flex-1 space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="truncate text-base font-semibold text-foreground">
                      {project.name}
                    </h2>
                    <Badge variant="secondary">{project.step_label}</Badge>
                    {project.is_shared && <Badge variant="muted">Shared</Badge>}
                  </div>
                  <div className="max-w-xl">
                    <ProgressDisplay progress={project.progress} />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {formatNumber(project.processed_documents)} /{" "}
                    {formatNumber(project.total_documents)} documents
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {project.can_open_project && (
                    <Button asChild variant="outline" size="sm">
                      <Link to={project.project_url}>
                        <FolderOpen className="size-4" /> Open
                      </Link>
                    </Button>
                  )}
                  {project.can_restart && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => restart.mutate(project.id)}
                      disabled={restart.isPending}
                    >
                      <RotateCcw className="size-4" /> Restart
                    </Button>
                  )}
                  {project.can_delete && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                      onClick={() => setPendingDelete(project)}
                      aria-label={`Delete ${project.name}`}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete this project?"
        description={
          pendingDelete
            ? `“${pendingDelete.name}” and all its data will be permanently removed.`
            : ""
        }
        confirmLabel="Delete"
        destructive
        loading={remove.isPending}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => pendingDelete && remove.mutate(pendingDelete.id)}
      />
    </>
  );
}
