import { cn } from "@/lib/cn";
import { PIPELINE_STAGES } from "@/lib/types";
import type { RunDetail, PipelineStage } from "@/lib/types";
import { Check, Hourglass, RotateCw, AlertTriangle } from "lucide-react";

type PhaseStatus = "pending" | "active" | "awaiting" | "completed" | "failed";

export function PipelineGraph({
  run,
}: {
  run: RunDetail;
  connection: "connecting" | "open" | "closed";
}) {
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

  return (
    <div className="card overflow-x-auto p-8">
      <div className="flex items-center min-w-max">
        {PIPELINE_STAGES.map((stage, idx) => {
          const status = statusFor(idx);
          const needsApproval = ["plan", "design", "sprint_plan"].includes(stage.name) && run.meta.auto_approve !== true;
          
          return (
            <div key={stage.name} className="flex items-center">
              {/* Node */}
              <div className={cn(
                "relative flex w-32 flex-col items-center justify-center rounded-xl border p-4 text-center transition-colors",
                status === "completed" && "border-emerald-500/40 bg-emerald-500/5",
                status === "active" && "border-accent bg-accent/5",
                status === "awaiting" && "border-amber-500/40 bg-amber-500/5",
                status === "failed" && "border-red-500/40 bg-red-500/5",
                status === "pending" && "border-line bg-surface"
              )}>
                {status === "active" && (
                  <span className="absolute -top-1 -right-1 flex h-3 w-3">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75"></span>
                    <span className="relative inline-flex h-3 w-3 rounded-full bg-accent"></span>
                  </span>
                )}
                
                <span className={cn(
                  "mb-2 grid h-8 w-8 place-items-center rounded-full border text-xs font-semibold",
                  status === "completed" && "border-emerald-500 bg-emerald-500/10 text-emerald-600",
                  status === "active" && "border-accent bg-accent/10 text-accent",
                  status === "awaiting" && "border-amber-500 bg-amber-500/10 text-amber-600",
                  status === "failed" && "border-red-500 bg-red-500/10 text-red-600",
                  status === "pending" && "border-line bg-surface text-faint"
                )}>
                  {status === "completed" ? (
                    <Check className="h-4 w-4" />
                  ) : status === "active" ? (
                    <RotateCw className="h-4 w-4 animate-spin" />
                  ) : status === "awaiting" ? (
                    <Hourglass className="h-4 w-4" />
                  ) : status === "failed" ? (
                    <AlertTriangle className="h-4 w-4" />
                  ) : (
                    idx + 1
                  )}
                </span>
                
                <span className={cn(
                  "font-display text-sm font-semibold",
                  status === "pending" ? "text-muted" : "text-ink"
                )}>
                  {stage.label}
                </span>
              </div>

              {/* Edge */}
              {idx < PIPELINE_STAGES.length - 1 && (
                <div className="flex w-16 items-center justify-center">
                  <div className={cn(
                    "h-[2px] w-full",
                    status === "completed" ? "bg-accent" : "bg-line"
                  )} />
                  
                  {/* Approval Gate Diamond */}
                  {needsApproval && (
                    <div className="absolute grid place-items-center">
                      <div className={cn(
                        "h-4 w-4 rotate-45 border",
                        status === "completed" 
                          ? "border-accent bg-accent/20" 
                          : status === "awaiting" 
                            ? "border-amber-500 bg-amber-500" 
                            : "border-line bg-surface"
                      )} title="Approval Gate" />
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
