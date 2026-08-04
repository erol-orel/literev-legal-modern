import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FilterX, SlidersHorizontal, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAppContext } from "@/hooks/use-app-context";
import { useToast } from "@/hooks/use-toast";
import {
  deleteProjectRefinement,
  type ProjectOverview,
  type RefinementItem,
} from "@/api/project-overview";
import { ApiError } from "@/lib/api-client";

export function RefinementList({
  projectId,
  refinements,
}: {
  projectId: string;
  refinements: RefinementItem[];
}) {
  const { api: apiUrls } = useAppContext();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<RefinementItem | null>(null);

  const remove = useMutation({
    mutationFn: (id: number) =>
      deleteProjectRefinement(apiUrls, projectId, id),
    onSuccess: (_data, id) => {
      queryClient.setQueryData<ProjectOverview>(["overview", projectId], (prev) =>
        prev
          ? { ...prev, refinements: prev.refinements.filter((r) => r.id !== id) }
          : prev,
      );
      toast({ variant: "success", title: "Refinement deleted" });
      setPending(null);
    },
    onError: (error) =>
      toast({
        variant: "destructive",
        title: "Delete failed",
        description:
          error instanceof ApiError ? error.messages.join(" ") : "Error.",
      }),
  });

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <SlidersHorizontal className="size-4 text-primary" /> Refinements
        </CardTitle>
      </CardHeader>
      <CardContent>
        {refinements.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-4 text-center">
            <FilterX className="size-5 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              No refinements yet. Build one to narrow the corpus and open it in
              the selection workspace.
            </p>
          </div>
        ) : (
          <ul className="space-y-2">
            {refinements.map((refinement) => (
              <li
                key={refinement.id}
                className="flex items-center gap-2 rounded-lg border p-2"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-foreground">
                    {refinement.name}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    by {refinement.owner_name}
                  </p>
                </div>
                <Button asChild variant="outline" size="sm">
                  <Link to={refinement.open_url}>Open</Link>
                </Button>
                {refinement.can_delete && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-8 text-destructive hover:bg-destructive/10 hover:text-destructive"
                    onClick={() => setPending(refinement)}
                    aria-label={`Delete ${refinement.name}`}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>

      <ConfirmDialog
        open={pending !== null}
        title="Delete refinement?"
        description={pending ? `“${pending.name}” will be removed.` : ""}
        confirmLabel="Delete"
        destructive
        loading={remove.isPending}
        onCancel={() => setPending(null)}
        onConfirm={() => pending && remove.mutate(pending.id)}
      />
    </Card>
  );
}
