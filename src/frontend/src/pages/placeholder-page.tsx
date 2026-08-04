import { Hammer } from "lucide-react";

import { PageHeader } from "@/components/common/page-header";
import { EmptyState } from "@/components/ui/empty-state";

/**
 * Temporary placeholder for routes rebuilt in later milestones of the modern
 * UI. Search, Project overview and RAG are the first flagship pages; the rest
 * follow.
 */
export function PlaceholderPage({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <EmptyState
        icon={Hammer}
        title="Coming in this rebuild"
        description="This workflow is being migrated to the new interface. It keeps the same backend behaviour — only the experience changes."
      />
    </>
  );
}
