import { Check, ChevronDown, Copy, ScanSearch } from "lucide-react";
import { useState } from "react";

import { parseSectionAnswers, type RagDocumentAnswer } from "@/api/rag";
import { ConfidenceBadge } from "@/components/rag/confidence";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useToast } from "@/hooks/use-toast";
import { buildAnswerCitation } from "@/lib/citation";
import { cn, formatDate } from "@/lib/utils";

/** One reasoning section (En fait / Subsomption / Conclusion) of an answer. */
function Section({ label, text }: { label: string; text: string }) {
  if (!text) return null;
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-primary">
        {label}
      </p>
      <p className="mt-0.5 whitespace-pre-line text-sm leading-relaxed text-foreground/90">
        {text}
      </p>
    </div>
  );
}

/**
 * A single cited decision in the evidence rail: a compact header (procedure,
 * language, date, confidence) that expands to reveal the structured reasoning
 * and the verbatim citation. Copy yields a ready-to-paste citation block.
 */
export function SourceCard({
  answer,
  defaultOpen = false,
  index,
}: {
  answer: RagDocumentAnswer;
  defaultOpen?: boolean;
  index?: number;
}) {
  const { toast } = useToast();
  const [open, setOpen] = useState(defaultOpen);
  const [copied, setCopied] = useState(false);
  const { document } = answer;
  const section = parseSectionAnswers(answer.answer);

  const meta = [document.procedure_type, document.decision_type, document.result]
    .filter(Boolean)
    .join(" · ");

  const copyCitation = async (event: React.MouseEvent) => {
    event.stopPropagation();
    try {
      await navigator.clipboard.writeText(buildAnswerCitation(answer));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
      toast({ variant: "success", title: "Citation copied" });
    } catch {
      toast({
        variant: "destructive",
        title: "Copy failed",
        description: "Clipboard is unavailable in this browser.",
      });
    }
  };

  return (
    <div className="overflow-hidden rounded-lg border bg-card transition-colors hover:border-primary/40">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
      >
        {index != null && (
          <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-semibold tabular-nums text-secondary-foreground">
            {index}
          </span>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-foreground">
              {document.procedure_type || "Decision"}
            </span>
            {document.language && (
              <Badge variant="outline" className="uppercase">
                {document.language}
              </Badge>
            )}
            {document.decision_date && (
              <span className="text-xs text-muted-foreground">
                {formatDate(document.decision_date)}
              </span>
            )}
          </div>
          {meta && (
            <p className="mt-0.5 truncate text-xs text-muted-foreground">{meta}</p>
          )}
        </div>
        {answer.confidence_score != null && (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="shrink-0">
                <ConfidenceBadge score={answer.confidence_score} />
              </span>
            </TooltipTrigger>
            <TooltipContent className="max-w-56 text-xs">
              Faithfulness: how well this answer is grounded in the decision's
              own text (higher = less room for hallucination). Open the decision
              to verify the cited passages.
            </TooltipContent>
          </Tooltip>
        )}
        <ChevronDown
          className={cn(
            "size-4 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
        />
      </button>

      {open && (
        <div className="space-y-3 border-t px-4 py-3">
          {section ? (
            <div className="space-y-3">
              <Section label="En fait" text={section.facts} />
              <Section label="Subsomption" text={section.subsumption} />
              <Section label="Conclusion" text={section.conclusion} />
            </div>
          ) : (
            <p className="whitespace-pre-line text-sm leading-relaxed text-foreground/90">
              {answer.answer}
            </p>
          )}
          {answer.citation &&
            (document.url_document ? (
              // The verbatim quote itself links into the decision, where the
              // cited passages are highlighted — one click from claim to source.
              <a
                href={document.url_document}
                target="_blank"
                rel="noreferrer"
                title="Open the decision with this passage highlighted"
                className="group block rounded-r border-l-2 border-primary/40 pl-3 text-sm italic text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
              >
                <span className="not-italic text-[0.7rem] font-semibold uppercase tracking-wide text-primary opacity-0 transition-opacity group-hover:opacity-100">
                  Verify passage →
                </span>
                <blockquote>{answer.citation}</blockquote>
              </a>
            ) : (
              <blockquote className="border-l-2 border-primary/40 pl-3 text-sm italic text-muted-foreground">
                {answer.citation}
              </blockquote>
            ))}
          <div className="flex items-center gap-2 pt-1">
            <Button variant="outline" size="sm" onClick={copyCitation}>
              {copied ? (
                <Check className="size-3.5 text-success" />
              ) : (
                <Copy className="size-3.5" />
              )}
              Copy citation
            </Button>
            {document.url_document && (
              <Button asChild variant="secondary" size="sm">
                <a href={document.url_document} target="_blank" rel="noreferrer">
                  <ScanSearch className="size-3.5" /> Verify in decision
                </a>
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
