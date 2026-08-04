import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, FolderOpen, Search as SearchIcon, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { PageHeader } from "@/components/common/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useAppContext } from "@/hooks/use-app-context";
import { useToast } from "@/hooks/use-toast";
import {
  deleteAllFinishedProjects,
  deleteProject,
  fetchHistoricalProjects,
  type HistoricalSort,
  type ProjectListItem,
} from "@/api/projects";
import { ApiError } from "@/lib/api-client";
import { formatDate, formatNumber } from "@/lib/utils";

export function HistoryPage() {
  const { api: apiUrls } = useAppContext();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [sortType, setSortType] = useState<HistoricalSort>("more_documents_first");
  const [pendingDelete, setPendingDelete] = useState<ProjectListItem | null>(null);
  const [deleteAllOpen, setDeleteAllOpen] = useState(false);

  const history = useQuery({
    queryKey: ["historical", search, sortType],
    queryFn: () => fetchHistoricalProjects(apiUrls, { search, sortType }),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["historical"] });

  const notifyError = (error: unknown) =>
    toast({
      variant: "destructive",
      title: "Action failed",
      description:
        error instanceof ApiError ? error.messages.join(" ") : "Unexpected error.",
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

  const removeAll = useMutation({
    mutationFn: () => deleteAllFinishedProjects(apiUrls),
    onSuccess: (data) => {
      toast({
        variant: "success",
        title: `Deleted ${data.deleted_count} project${data.deleted_count === 1 ? "" : "s"}`,
      });
      setDeleteAllOpen(false);
      invalidate();
    },
    onError: notifyError,
  });

  const projects = history.data?.projects ?? [];

  return (
    <>
      <PageHeader
        title="Project history"
        description="Revisit completed analyses. Search by name or query and reopen any project."
        actions={
          projects.length > 0 ? (
            <Button
              variant="outline"
              className="text-destructive hover:bg-destructive/10"
              onClick={() => setDeleteAllOpen(true)}
            >
              <Trash2 className="size-4" /> Delete all
            </Button>
          ) : null
        }
      />

      <div className="mb-6 flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <SearchIcon className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search projects…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select
          value={sortType}
          onValueChange={(value) => setSortType(value as HistoricalSort)}
        >
          <SelectTrigger className="sm:w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="more_documents_first">Most documents first</SelectItem>
            <SelectItem value="less_documents_first">Fewest documents first</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {history.isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : projects.length === 0 ? (
        <EmptyState
          icon={Archive}
          title={search ? "No matching projects" : "No completed projects yet"}
          description={
            search
              ? "Try a different search term."
              : "Completed analyses will be archived here."
          }
        />
      ) : (
        <div className="space-y-3">
          {projects.map((project) => (
            <Card key={project.id}>
              <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="truncate text-base font-semibold text-foreground">
                      {project.name}
                    </h2>
                    {project.is_shared && <Badge variant="muted">Shared</Badge>}
                  </div>
                  <p className="truncate font-mono text-xs text-muted-foreground">
                    {project.query || "—"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatNumber(project.total_documents)} documents ·{" "}
                    {formatDate(project.creation_date)}
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

      <ConfirmDialog
        open={deleteAllOpen}
        title="Delete all completed projects?"
        description="Every completed project you own will be permanently removed. This cannot be undone."
        confirmLabel="Delete all"
        destructive
        loading={removeAll.isPending}
        onCancel={() => setDeleteAllOpen(false)}
        onConfirm={() => removeAll.mutate()}
      />
    </>
  );
}
