import { Check, Hourglass, RotateCw, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/cn";
import { PIPELINE_STAGES } from "@/lib/types";
import type { RunDetail, PipelineStage } from "@/lib/types";

type PhaseStatus = "pending" | "active" | "awaiting" | "completed" | "failed";

export function PipelineKanban({
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
    <div className="flex gap-4 overflow-x-auto pb-4">
      {PIPELINE_STAGES.map((stage, idx) => {
        const status = statusFor(idx);
        const artifact = run.artifacts.find(a => a.kind === stage.artifact_kind);

        return (
          <div key={stage.name} className="flex-1 min-w-[200px] shrink-0">
            {/* Column Header */}
            <div className="mb-3 flex items-center justify-between">
              <h3 className={cn(
                "font-display text-sm font-semibold",
                status === "pending" ? "text-muted" : "text-ink"
              )}>
                {stage.label}
              </h3>
              <div className="flex items-center">
                {status === "active" && (
                  <span className="flex h-2 w-2">
                    <span className="absolute inline-flex h-2 w-2 animate-ping rounded-full bg-accent opacity-75"></span>
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-accent"></span>
                  </span>
                )}
              </div>
            </div>

            {/* Card */}
            <div className={cn(
              "card flex h-32 flex-col justify-between p-4 transition-colors",
              status === "active" && "border-accent ring-1 ring-accent",
              status === "completed" && "bg-surface-2",
              status === "awaiting" && "border-amber-500/40"
            )}>
              <div className="flex items-start justify-between">
                <span className={cn(
                  "grid h-6 w-6 place-items-center rounded-md border text-xs font-semibold",
                  status === "completed" && "border-emerald-500 bg-emerald-500/10 text-emerald-600",
                  status === "active" && "border-accent bg-accent/10 text-accent",
                  status === "awaiting" && "border-amber-500 bg-amber-500/10 text-amber-600",
                  status === "failed" && "border-red-500 bg-red-500/10 text-red-600",
                  status === "pending" && "border-line bg-surface text-faint"
                )}>
                  {status === "completed" ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : status === "active" ? (
                    <RotateCw className="h-3 w-3 animate-spin" />
                  ) : status === "awaiting" ? (
                    <Hourglass className="h-3 w-3" />
                  ) : status === "failed" ? (
                    <AlertTriangle className="h-3 w-3" />
                  ) : (
                    idx + 1
                  )}
                </span>
                
                {status === "awaiting" && (
                  <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-amber-600">
                    Needs Review
                  </span>
                )}
              </div>
              
              <div className="mt-2 text-xs">
                {artifact ? (
                  <div className="text-muted">
                    {stage.artifact_kind === "prd" && `${(artifact.content as any).user_stories?.length || 0} stories`}
                    {stage.artifact_kind === "system_design" && `${(artifact.content as any).components?.length || 0} components`}
                    {stage.artifact_kind === "sprint_plan" && `${(artifact.content as any).sprints?.length || 0} sprints`}
                    {stage.artifact_kind === "code" && `${(artifact.content as any).files?.length || 0} files`}
                    {stage.artifact_kind === "test_suite" && `${(artifact.content as any).test_files?.length || 0} tests`}
                  </div>
                ) : (
                  <div className="text-faint">{stage.description}</div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
