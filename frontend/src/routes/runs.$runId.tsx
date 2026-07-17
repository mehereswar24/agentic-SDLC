import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowLeft,
  AlertTriangle,
  Clock,
  Cpu,
  Download,
  RefreshCw,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, downloadCodeZip } from "@/lib/api";
import { useRunLive } from "@/lib/useRunLive";
import type { ClarifyingQuestions, PipelineStage } from "@/lib/types";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/StatusBadge";
import { RunTimeline } from "@/components/RunTimeline";
import { ApprovalGate } from "@/components/ApprovalGate";
import { ClarificationsForm } from "@/components/ClarificationsForm";
import { ArtifactPanel } from "@/components/ArtifactPanel";
import { ChatDock } from "@/components/ChatDock";

export const Route = createFileRoute("/runs/$runId")({
  head: () => ({ meta: [{ title: "Run · Agentic SDLC Orchestrator" }] }),
  component: RunDetailPage,
});

function RunDetailPage() {
  const { runId } = Route.useParams();
  const { run, isLoading, connection, activity } = useRunLive(runId);

  const qc = useQueryClient();
  const [retrying, setRetrying] = useState(false);
  const [zipping, setZipping] = useState(false);

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

  const totalTokens = run.steps.reduce(
    (a, s) => a + (s.tokens_in ?? 0) + (s.tokens_out ?? 0),
    0,
  );
  const totalLatency = run.steps.reduce((a, s) => a + (s.latency_ms ?? 0), 0);
  const hasCode = run.artifacts.some((a) => a.kind === "code");

  // Which gate to render at the paused stage (inside the timeline).
  const pausedStage = run.meta.last_completed_stage as PipelineStage | undefined;
  let gate: React.ReactNode = null;
  if (run.status === "awaiting_human" && pausedStage) {
    if (pausedStage === "clarify") {
      const questions = run.artifacts
        .filter((a) => a.kind === "clarifying_questions")
        .sort((a, b) => b.version - a.version)[0]?.content as
        | ClarifyingQuestions
        | undefined;
      gate = questions ? (
        <ClarificationsForm runId={run.id} questions={questions} />
      ) : (
        <ApprovalGate runId={run.id} completedStage={pausedStage} artifacts={run.artifacts} />
      );
    } else {
      gate = (
        <ApprovalGate
          runId={run.id}
          completedStage={pausedStage}
          artifacts={run.artifacts}
        />
      );
    }
  }

  const handleZip = async () => {
    setZipping(true);
    try {
      await downloadCodeZip(run.id);
    } catch (e: any) {
      toast.error(e.message ?? "Download failed");
    } finally {
      setZipping(false);
    }
  };

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
          <div className="flex items-center gap-3">
            {hasCode && (
              <button
                onClick={handleZip}
                disabled={zipping}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-secondary disabled:opacity-50"
              >
                <Download className={cn("h-3.5 w-3.5", zipping && "animate-bounce")} />
                Download ZIP
              </button>
            )}
            <StatusBadge status={run.status} />
          </div>
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
          <span>{run.steps.length} steps</span>
        </div>
      </div>

      {run.status === "failed" && run.error && (
        <div className="glass float-in mt-6 flex items-start gap-3 rounded-2xl border border-destructive/30 p-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
          <div className="flex-1">
            <p className="text-sm font-medium text-destructive">Run failed</p>
            <p className="mb-3 text-xs text-muted-foreground">{run.error}</p>
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

      {/* Pipeline timeline (gate renders inline at the paused stage) */}
      <div className="float-in mt-6">
        <RunTimeline run={run} connection={connection} activity={activity} gate={gate} />
      </div>

      {/* Artifacts */}
      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold text-foreground">Artifacts</h2>
        <ArtifactPanel artifacts={run.artifacts} runId={run.id} runStatus={run.status} />
      </section>

      <ChatDock runId={run.id} status={run.status} />
    </div>
  );
}
