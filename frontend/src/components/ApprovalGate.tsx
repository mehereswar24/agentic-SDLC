import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, X, PenLine, MessageSquare, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  PIPELINE_STAGES,
  type ArtifactView,
  type PipelineStage,
  type PRD,
  type ReviewReport,
  type ValidationReport,
} from "@/lib/types";
import { LiquidButton } from "@/components/ui/button";
import { ReviewReportCard } from "@/components/ReviewReportCard";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

const STAGE_REVIEWERS: Partial<Record<PipelineStage, string[]>> = {
  plan: ["planner_reviewer"],
  design: ["architecture_reviewer", "security_reviewer"],
};

const STAGE_VALIDATION: Partial<Record<PipelineStage, string>> = {
  plan: "prd",
  design: "system_design",
};

const REVISABLE: PipelineStage[] = ["plan", "design", "sprint_plan"];

function latestBy<T>(
  artifacts: ArtifactView[],
  kind: string,
  keyOf: (content: T) => string,
): Map<string, T> {
  const map = new Map<string, { version: number; content: T }>();
  for (const a of artifacts) {
    if (a.kind !== kind) continue;
    const content = a.content as T;
    const key = keyOf(content);
    const existing = map.get(key);
    if (!existing || a.version > existing.version) {
      map.set(key, { version: a.version, content });
    }
  }
  return new Map([...map.entries()].map(([k, v]) => [k, v.content]));
}

export function ApprovalGate({
  runId,
  completedStage,
  artifacts,
}: {
  runId: string;
  completedStage: PipelineStage;
  artifacts: ArtifactView[];
}) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState<"approve" | "reject" | "revise" | null>(null);
  const [revising, setRevising] = useState(false);
  const [feedback, setFeedback] = useState("");

  const stageLabel =
    PIPELINE_STAGES.find((s) => s.name === completedStage)?.label ?? completedStage;

  const reviews = useMemo(() => {
    const wanted = STAGE_REVIEWERS[completedStage] ?? [];
    const byReviewer = latestBy<ReviewReport>(
      artifacts,
      "review_report",
      (r) => r.reviewer,
    );
    return wanted
      .map((r) => byReviewer.get(r))
      .filter((r): r is ReviewReport => r != null);
  }, [artifacts, completedStage]);

  const validation = useMemo(() => {
    const kind = STAGE_VALIDATION[completedStage];
    if (!kind) return null;
    const byKind = latestBy<ValidationReport>(
      artifacts,
      "validation_report",
      (v) => v.artifact_kind,
    );
    return byKind.get(kind) ?? null;
  }, [artifacts, completedStage]);

  const sectionConfidence = useMemo(() => {
    if (completedStage !== "plan") return null;
    const prd = artifacts
      .filter((a) => a.kind === "prd")
      .sort((a, b) => b.version - a.version)[0]?.content as PRD | undefined;
    const entries = Object.entries(prd?.section_confidence ?? {});
    return entries.length > 0 ? entries : null;
  }, [artifacts, completedStage]);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["run", runId] });
    qc.invalidateQueries({ queryKey: ["runs"] });
  };

  const decide = async (
    decision: "approve" | "reject" | "revise",
    fb?: string,
  ) => {
    setBusy(decision);
    try {
      await api.decideRun(runId, { decision, feedback: fb });
      if (decision === "approve") toast.success("Approved — resuming pipeline");
      else if (decision === "revise") toast.success("Revision requested");
      else toast("Run terminated");
      setRevising(false);
      setFeedback("");
      refresh();
    } catch (e: any) {
      toast.error(e.message ?? `Failed to ${decision}`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="glass-strong float-in rounded-3xl p-6">
      <div className="flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-foreground text-background">
          <MessageSquare className="h-4 w-4" />
        </span>
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            Review required — {stageLabel}
          </h3>
          <p className="text-xs text-muted-foreground">
            Approve to continue, request changes with feedback, or reject to
            terminate this run.
          </p>
        </div>
      </div>

      {/* Reviewer context */}
      {(reviews.length > 0 || validation || sectionConfidence) && (
        <div className="mt-4 space-y-2.5">
          {reviews.map((r) => (
            <ReviewReportCard key={r.reviewer} report={r} />
          ))}
          {validation && (
            <div className="rounded-xl border border-border/60 bg-secondary/40 p-3.5">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-foreground">
                  Alignment with your brief
                </span>
                <span className="text-sm font-semibold tabular-nums text-foreground">
                  {validation.score}
                  <span className="text-[10px] font-normal text-muted-foreground/70">
                    /100
                  </span>
                </span>
              </div>
              {validation.issues.length > 0 && (
                <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-[12px] text-muted-foreground marker:text-muted-foreground/50">
                  {validation.issues.map((i, idx) => (
                    <li key={idx}>{i}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {sectionConfidence && (
            <div className="rounded-xl border border-border/60 bg-secondary/40 p-3.5">
              <div className="text-xs font-semibold text-foreground">
                Section confidence
              </div>
              <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
                {sectionConfidence.map(([section, score]) => (
                  <div key={section} className="flex items-center gap-2">
                    <span className="w-32 truncate text-[11px] text-muted-foreground">
                      {section.replace(/_/g, " ")}
                    </span>
                    <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-secondary">
                      <span
                        className={cn(
                          "block h-full rounded-full",
                          score < 70 ? "bg-amber-500" : "bg-foreground",
                        )}
                        style={{ width: `${Math.max(4, Math.min(100, score))}%` }}
                      />
                    </span>
                    <span
                      className={cn(
                        "w-7 text-right text-[11px] tabular-nums",
                        score < 70
                          ? "font-semibold text-amber-600 dark:text-amber-400"
                          : "text-muted-foreground",
                      )}
                    >
                      {score}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Revise feedback */}
      {revising && (
        <div className="float-in mt-4">
          <textarea
            autoFocus
            rows={3}
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder={`What should change in the ${stageLabel.toLowerCase()}? Be specific — the agent regenerates it from this feedback.`}
            className="w-full resize-none rounded-xl border border-input bg-background p-3 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-3">
        {!revising ? (
          <>
            <LiquidButton
              disabled={busy !== null}
              size="lg"
              onClick={() => decide("approve")}
            >
              {busy === "approve" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Check className="h-4 w-4" />
              )}
              Approve &amp; continue
            </LiquidButton>

            {REVISABLE.includes(completedStage) && (
              <LiquidButton
                disabled={busy !== null}
                size="lg"
                variant="outline"
                onClick={() => setRevising(true)}
              >
                <PenLine className="h-4 w-4" />
                Request changes
              </LiquidButton>
            )}

            <AlertDialog>
              <AlertDialogTrigger asChild>
                <LiquidButton disabled={busy !== null} size="lg" variant="destructive">
                  {busy === "reject" ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <X className="h-4 w-4" />
                  )}
                  Reject
                </LiquidButton>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Terminate this run?</AlertDialogTitle>
                  <AlertDialogDescription>
                    Rejecting cancels the run permanently. If you want the{" "}
                    {stageLabel.toLowerCase()} redone instead, use "Request
                    changes".
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Keep run</AlertDialogCancel>
                  <AlertDialogAction onClick={() => decide("reject")}>
                    Reject &amp; terminate
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </>
        ) : (
          <>
            <LiquidButton
              disabled={busy !== null || !feedback.trim()}
              size="lg"
              onClick={() => decide("revise", feedback.trim())}
            >
              {busy === "revise" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <PenLine className="h-4 w-4" />
              )}
              Send for revision
            </LiquidButton>
            <LiquidButton
              disabled={busy !== null}
              size="lg"
              variant="outline"
              onClick={() => {
                setRevising(false);
                setFeedback("");
              }}
            >
              Cancel
            </LiquidButton>
          </>
        )}
      </div>
    </div>
  );
}
