import { useState } from "react";
import { Check, AlertTriangle, ChevronDown, ChevronRight, Hourglass, RotateCw } from "lucide-react";

import { cn } from "@/lib/cn";
import { PIPELINE_STAGES } from "@/lib/types";
import type { RunDetail, PipelineStage } from "@/lib/types";

type PhaseStatus = "pending" | "active" | "awaiting" | "completed" | "failed";

const STATUS_PILL: Record<PhaseStatus, string> = {
  pending: "border-line bg-surface-2 text-faint",
  active: "border-accent/40 bg-accent-soft text-accent-ink",
  awaiting: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  completed: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  failed: "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300",
};

const MARKER: Record<PhaseStatus, string> = {
  pending: "border-line bg-surface text-faint",
  active: "border-accent bg-accent-soft text-accent",
  awaiting: "border-amber-500 bg-amber-500/15 text-amber-600 dark:text-amber-400",
  completed: "border-accent bg-accent text-white",
  failed: "border-red-500 bg-red-500/15 text-red-500",
};

export function PipelineStepper({
  run,
  connection,
}: {
  run: RunDetail;
  connection: "connecting" | "open" | "closed";
}) {
  const [expandedPhase, setExpandedPhase] = useState<PipelineStage | null>(null);
  
  const completed: Record<PipelineStage, boolean> = {
    plan: run.artifacts.some((a) => a.kind === "prd"),
    design: run.artifacts.some((a) => a.kind === "system_design"),
    sprint_plan: run.artifacts.some((a) => a.kind === "sprint_plan"),
    build: run.artifacts.some((a) => a.kind === "code"),
    test: run.artifacts.some((a) => a.kind === "test_suite"),
  };
  
  const frontierIdx = PIPELINE_STAGES.findIndex((s) => !completed[s.name]);

  const statusFor = (idx: number): PhaseStatus => {
    const key = PIPELINE_STAGES[idx].name;
    if (completed[key]) return "completed";
    if (idx !== frontierIdx) return "pending";
    switch (run.status) {
      case "failed": return "failed";
      case "awaiting_human": return "awaiting";
      case "running": return "active";
      default: return "pending";
    }
  };

  const completedCount = PIPELINE_STAGES.filter((s) => completed[s.name]).length;
  const activeFraction = run.status === "running" && frontierIdx >= 0 ? 0.5 : 0;
  const progress = Math.min(1, (completedCount + activeFraction) / PIPELINE_STAGES.length);

  return (
    <div className="space-y-4">
      {/* Summary Header */}
      <div className="card p-5">
        <div className="flex items-center justify-between gap-3">
          <h3 className="eyebrow">Pipeline Progress</h3>
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.14em]",
              connection === "open"
                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                : "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
            )}
            title={connection === "open" ? "Live stream connected" : "Reconnecting…"}
          >
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                connection === "open" ? "bg-emerald-500" : "animate-pulse bg-amber-500",
              )}
            />
            {connection === "open" ? "Live" : "Reconnecting"}
          </span>
        </div>

        <div className="mt-4 flex items-baseline justify-between">
          <span className="font-display text-2xl font-semibold text-ink">
            {Math.round(progress * 100)}%
          </span>
          <span className="text-[11px] uppercase tracking-[0.12em] text-faint">
            {completedCount} / {PIPELINE_STAGES.length} phases complete
          </span>
        </div>

        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-700 ease-out"
            style={{ width: `${progress * 100}%` }}
          />
        </div>
      </div>

      {/* Stepper view */}
      <div className="card p-4 sm:p-5">
        <div className="space-y-4">
          {PIPELINE_STAGES.map((stage, idx) => {
            const status = statusFor(idx);
            const isExpanded = expandedPhase === stage.name;
            const canExpand = completed[stage.name];
            
            // Get artifact summary
            const artifact = run.artifacts.find(a => a.kind === stage.artifact_kind);
            
            return (
              <div key={stage.name} className="relative pl-10">
                {/* Connecting line */}
                {idx < PIPELINE_STAGES.length - 1 && (
                  <div className={cn(
                    "absolute left-4 top-10 bottom-[-16px] w-[2px] -ml-px",
                    status === "completed" ? "bg-accent/50" : "bg-line"
                  )} />
                )}

                {/* Status marker */}
                <span
                  className={cn(
                    "absolute left-0 top-1 grid h-8 w-8 place-items-center rounded-full border text-sm font-semibold",
                    MARKER[status]
                  )}
                >
                  {status === "completed" ? (
                    <Check className="h-4 w-4" strokeWidth={2.5} />
                  ) : status === "active" ? (
                    <RotateCw className="h-4 w-4 animate-spin" />
                  ) : status === "awaiting" ? (
                    <Hourglass className="h-4 w-4" />
                  ) : status === "failed" ? (
                    <AlertTriangle className="h-4 w-4" />
                  ) : (
                    <span className="text-[11px]">{idx + 1}</span>
                  )}
                </span>

                <div 
                  className={cn(
                    "rounded-lg border border-transparent p-3 transition-colors",
                    canExpand ? "hover:border-line-soft hover:bg-surface-2 cursor-pointer" : ""
                  )}
                  onClick={() => {
                    if (canExpand) {
                      setExpandedPhase(isExpanded ? null : stage.name);
                    }
                  }}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className={cn(
                        "font-display font-semibold",
                        status === "pending" ? "text-muted" : "text-ink"
                      )}>
                        {stage.label}
                      </h4>
                      <p className="text-[12px] text-muted-foreground">{stage.description}</p>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        "rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.1em]",
                        STATUS_PILL[status]
                      )}>
                        {status}
                      </span>
                      {canExpand && (
                        isExpanded ? <ChevronDown className="h-4 w-4 text-muted" /> : <ChevronRight className="h-4 w-4 text-muted" />
                      )}
                    </div>
                  </div>

                  {/* Expanded artifact preview */}
                  {isExpanded && artifact && (
                    <div className="mt-4 rounded bg-surface p-3 text-xs border border-line-soft">
                      {stage.artifact_kind === "prd" && (
                        <div>
                          <strong className="text-ink">{(artifact.content as any).title}</strong>
                          <div className="text-faint mt-1">{(artifact.content as any).user_stories?.length || 0} user stories</div>
                        </div>
                      )}
                      {stage.artifact_kind === "system_design" && (
                        <div>
                          <strong className="text-ink">Architecture</strong>
                          <div className="text-faint mt-1">{(artifact.content as any).components?.length || 0} components</div>
                        </div>
                      )}
                      {stage.artifact_kind === "sprint_plan" && (
                        <div>
                          <strong className="text-ink">Sprint Plan</strong>
                          <div className="text-faint mt-1">{(artifact.content as any).sprints?.length || 0} sprints</div>
                        </div>
                      )}
                      {stage.artifact_kind === "code" && (
                        <div>
                          <strong className="text-ink">Codebase</strong>
                          <div className="text-faint mt-1">{(artifact.content as any).files?.length || 0} files</div>
                        </div>
                      )}
                      {stage.artifact_kind === "test_suite" && (
                        <div>
                          <strong className="text-ink">Test Suite</strong>
                          <div className="text-faint mt-1">{(artifact.content as any).test_files?.length || 0} test files</div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
