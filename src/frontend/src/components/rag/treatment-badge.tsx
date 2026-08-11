import { AlertTriangle, Check, GitBranch, MessageSquareWarning } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

type BadgeVariant = "destructive" | "warning" | "success" | "outline";

const CONFIG: Record<
  string,
  {
    label: string;
    variant: BadgeVariant;
    icon: typeof AlertTriangle;
    tooltip: string;
  }
> = {
  overruled: {
    label: "Overruled",
    variant: "destructive",
    icon: AlertTriangle,
    tooltip:
      "A later decision overruled this one (revirement de jurisprudence). Verify it is still good law before relying on it.",
  },
  criticized: {
    label: "Criticised",
    variant: "warning",
    icon: MessageSquareWarning,
    tooltip:
      "A later decision criticised or doubted this one. Read the treating decision before relying on it.",
  },
  distinguished: {
    label: "Distinguished",
    variant: "outline",
    icon: GitBranch,
    tooltip:
      "A later decision distinguished this one on its facts — it may not control your case.",
  },
  followed: {
    label: "Followed",
    variant: "success",
    icon: Check,
    tooltip: "A later decision confirmed and followed this one.",
  },
};

/**
 * The "is this still good law?" signal for a cited decision, from the citation
 * graph's treatment classification. Renders nothing for a neutral mention
 * (`cited`) or when no treatment is known yet — so it is safe to always mount.
 */
export function TreatmentBadge({
  treatment,
  className,
}: {
  treatment?: string;
  className?: string;
}) {
  if (!treatment) return null;
  const config = CONFIG[treatment];
  if (!config) return null;
  const Icon = config.icon;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant={config.variant} className={className}>
          <Icon className="mr-1 size-3" />
          {config.label}
        </Badge>
      </TooltipTrigger>
      <TooltipContent className="max-w-56 text-xs">
        {config.tooltip}
      </TooltipContent>
    </Tooltip>
  );
}
