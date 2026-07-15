import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowLeft,
  ListTree,
  KanbanSquare,
  GitBranch,
  AlertTriangle,
  Clock,
  Cpu,
  RefreshCw,
} from "lucide-react";
import { useRun, useArtifacts, useSteps, useRunRealtime } from "@/lib/api.tanstack";
import { api } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useRunDriver } from "@/hooks/useRunDriver";
import { StatusBadge } from "@/components/StatusBadge";
import { PipelineStepper } from "@/components/PipelineStepper";
import { PipelineKanban } from "@/components/PipelineKanban";
import { PipelineGraph } from "@/components/PipelineGraph";
import { ApprovalGate } from "@/components/ApprovalGate";
import { ArtifactPanel } from "@/components/ArtifactPanel";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/runs/$runId")({
  head: () => ({ meta: [{ title: "Run · Agentic SDLC Orchestrator" }] }),
  component: RunDetail,
});

type ViewMode = "stepper" | "kanban" | "graph";

const VIEWS: { key: ViewMode; label: string; icon: React.ElementType }[] = [
  { key: "stepper", label: "Stepper", icon: ListTree },
  { key: "kanban", label: "Kanban", icon: KanbanSquare },
  { key: "graph", label: "Graph", icon: GitBranch },
];

function RunDetail() {
  const { runId } = Route.useParams();
  useRunRealtime(runId);
  const { data: run, isLoading } = useRun(runId);
  const { data: artifacts } = useArtifacts(runId);
  const { data: steps } = useSteps(runId);
  useRunDriver(run ? { ...run, steps: steps ?? [], artifacts: artifacts ?? [] } : null);

  const [view, setView] = useState<ViewMode>("stepper");
  const qc = useQueryClient();
  const [retrying, setRetrying] = useState(false);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Loading run…
      </div>
    );
  }

  if (!run) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-24 text-center">
        <h1 className="text-lg font-semibold text-foreground">Run not found</h1>
        <Link to="/" className="mt-4 inline-block text-sm text-muted-foreground underline">
          Back to dashboard
        </Link>
      </div>
    );
  }

  const totalTokens = (steps ?? []).reduce(
    (a, s) => a + (s.tokens_in ?? 0) + (s.tokens_out ?? 0),
    0,
  );
  const totalLatency = (steps ?? []).reduce((a, s) => a + (s.latency_ms ?? 0), 0);

  return (
    <div className="mx-auto min-h-screen max-w-5xl px-5 py-10 sm:px-8">
      {/* Header */}
      <div className="float-in">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Dashboard
        </Link>
        <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
          <h1 className="max-w-2xl text-xl font-semibold tracking-tight text-foreground">
            {run.prompt}
          </h1>
          <StatusBadge status={run.status} />
        </div>
        <div className="mt-2 flex flex-wrap gap-4 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <Cpu className="h-3.5 w-3.5" />
            {totalTokens.toLocaleString()} tokens
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5" />
            {(totalLatency / 1000).toFixed(1)}s agent time
          </span>
          <span>{steps?.length ?? 0} steps</span>
        </div>
      </div>

      {run.status === "failed" && run.error && (
        <div className="glass float-in mt-6 flex items-start gap-3 rounded-2xl border border-destructive/30 p-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
          <div className="flex-1">
            <p className="text-sm font-medium text-destructive">Run failed</p>
            <p className="text-xs text-muted-foreground mb-3">{run.error}</p>
            <button
              disabled={retrying}
              onClick={async () => {
                setRetrying(true);
                try {
                  await api.retryRun(run.id);
                  toast.success("Run resumed");
                  qc.invalidateQueries({ queryKey: ["run", run.id] });
                } catch (e: any) {
                  toast.error(e.message || "Failed to retry run");
                } finally {
                  setRetrying(false);
                }
              }}
              className="inline-flex items-center gap-1.5 rounded-lg bg-destructive/10 px-3 py-1.5 text-xs font-medium text-destructive transition-colors hover:bg-destructive/20 disabled:opacity-50"
            >
              <RefreshCw className={cn("h-3.5 w-3.5", retrying && "animate-spin")} />
              Try again
            </button>
          </div>
        </div>
      )}

      {/* View switcher */}
      <div className="float-in mt-6 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">Pipeline</h2>
        <div className="glass inline-flex gap-1 rounded-xl p-1">
          {VIEWS.map((v) => (
            <button
              key={v.key}
              onClick={() => setView(v.key)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                view === v.key
                  ? "bg-foreground text-background"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <v.icon className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">{v.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4">
        {view === "stepper" && <PipelineStepper run={{ ...run, steps: steps ?? [], artifacts: artifacts ?? [] }} connection="open" />}
        {view === "kanban" && <PipelineKanban run={{ ...run, steps: steps ?? [], artifacts: artifacts ?? [] }} connection="open" />}
        {view === "graph" && <PipelineGraph run={{ ...run, steps: steps ?? [], artifacts: artifacts ?? [] }} connection="open" />}
      </div>

      {/* Approval gate */}
      {run.status === "awaiting_human" && run.meta.awaiting_stage && (
        <div className="mt-6">
          <ApprovalGate runId={run.id} stage={run.meta.awaiting_stage} />
        </div>
      )}

      {/* Artifacts */}
      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold text-foreground">Artifacts</h2>
        <ArtifactPanel artifacts={artifacts ?? []} runId={run.id} />
      </section>
    </div>
  );
}
