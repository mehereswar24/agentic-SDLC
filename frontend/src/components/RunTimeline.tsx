import { Fragment, useEffect, useState, type ReactNode } from "react";
import { AlertTriangle, Check, Clock, Hourglass, RotateCw } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ConnectionState, RunActivity } from "@/lib/useRunLive";
import {
  PIPELINE_STAGES,
  stageForNode,
  type AgentStepView,
  type ArtifactView,
  type PipelineStage,
  type RunDetail,
} from "@/lib/types";

type StageStatus = "pending" | "active" | "awaiting" | "completed" | "failed";

const STATUS_LABEL: Record<StageStatus, string> = {
  pending: "Pending",
  active: "In progress",
  awaiting: "Review required",
  completed: "Completed",
  failed: "Failed",
};

const MARKER: Record<StageStatus, string> = {
  pending: "border-border bg-card text-muted-foreground/70",
  active: "border-foreground bg-secondary text-foreground",
  awaiting: "border-amber-500/70 bg-secondary text-foreground",
  completed: "border-foreground bg-foreground text-background",
  failed: "border-destructive bg-destructive/10 text-destructive",
};

const PILL: Record<StageStatus, string> = {
  pending: "border-border bg-secondary text-muted-foreground/70",
  active: "border-foreground/20 bg-foreground/10 text-foreground",
  awaiting: "border-border bg-secondary text-foreground",
  completed: "border-border bg-secondary text-muted-foreground",
  failed: "border-destructive/30 bg-destructive/10 text-destructive",
};

function fmtDuration(ms: number): string {
  const total = Math.floor(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function stepKey(s: AgentStepView): string {
  return `${s.id}-${s.created_at}`;
}

function artifactSummary(kind: string, artifacts: ArtifactView[]): string | null {
  const versions = artifacts
    .filter((a) => a.kind === kind)
    .sort((a, b) => b.version - a.version);
  const latest = versions[0];
  if (!latest) return null;
  const c = latest.content as Record<string, any>;
  const v = versions.length > 1 ? ` · v${latest.version}` : "";
  switch (kind) {
    case "clarifying_questions":
      return `${c.questions?.length ?? 0} questions${v}`;
    case "prd":
      return `"${c.title ?? "PRD"}" · ${c.user_stories?.length ?? 0} stories${v}`;
    case "system_design":
      return `${c.components?.length ?? 0} components · ${c.data_models?.length ?? 0} models${v}`;
    case "sprint_plan":
      return `${c.sprints?.length ?? 0} sprint${(c.sprints?.length ?? 0) === 1 ? "" : "s"}${v}`;
    case "code":
      return `${c.files?.length ?? 0} files · ${c.project_name ?? ""}${v}`;
    case "test_suite":
      return `${c.test_files?.length ?? 0} test files${v}`;
    default:
      return null;
  }
}

export function RunTimeline({
  run,
  connection,
  activity,
  gate,
}: {
  run: RunDetail;
  connection: ConnectionState;
  activity: RunActivity | null;
  gate?: ReactNode;
}) {
  const completed: Record<string, boolean> = {};
  for (const s of PIPELINE_STAGES) {
    completed[s.name] = run.artifacts.some((a) => a.kind === s.artifact_kind);
  }
  const frontierIdx = PIPELINE_STAGES.findIndex((s) => !completed[s.name]);
  const pausedStage =
    run.status === "awaiting_human"
      ? (run.meta.last_completed_stage as PipelineStage | undefined)
      : undefined;

  const statusFor = (idx: number): StageStatus => {
    const stage = PIPELINE_STAGES[idx];
    if (stage.name === pausedStage) return "awaiting";
    if (completed[stage.name]) return "completed";
    if (idx !== frontierIdx) return "pending";
    switch (run.status) {
      case "failed":
        return "failed";
      case "running":
      case "pending":
        return "active";
      default:
        return "pending";
    }
  };

  const stepsByStage: Record<string, AgentStepView[]> = {};
  for (const s of PIPELINE_STAGES) stepsByStage[s.name] = [];
  for (const step of run.steps) {
    const stage = stageForNode(step.node, {
      artifact_kind: step.input?.artifact_kind as string | undefined,
    });
    if (stage) stepsByStage[stage].push(step);
  }

  const isLive = run.status === "running" || run.status === "pending";
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  // Live elapsed clock — initialized on mount so SSR output stays stable.
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    setNow(Date.now());
    if (!isLive) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [isLive]);

  const startMs = new Date(run.created_at).getTime();
  const endMs = isLive && now ? now : new Date(run.updated_at).getTime();
  const elapsedMs = Math.max(0, endMs - startMs);

  const completedCount = PIPELINE_STAGES.filter((s) => completed[s.name]).length;
  const activeFraction = run.status === "running" && frontierIdx >= 0 ? 0.5 : 0;
  const progress = Math.min(1, (completedCount + activeFraction) / PIPELINE_STAGES.length);

  const tokens = run.steps.reduce(
    (a, s) => a + (s.tokens_in ?? 0) + (s.tokens_out ?? 0),
    0,
  );

  const selectedStep =
    selectedKey != null
      ? run.steps.find((s) => stepKey(s) === selectedKey) ?? null
      : null;

  return (
    <div className="space-y-4">
      {/* Summary card */}
      <div className="glass rounded-2xl p-5">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Pipeline
          </h3>
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border border-border bg-secondary px-2.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.14em] text-muted-foreground",
            )}
            title={
              connection === "open"
                ? "Live event stream connected"
                : connection === "polling"
                  ? "Stream unavailable — polling every 3s"
                  : "Connecting to live stream…"
            }
          >
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                connection === "open"
                  ? "bg-emerald-500"
                  : connection === "polling"
                    ? "bg-amber-500"
                    : "animate-pulse bg-muted-foreground",
              )}
            />
            {connection === "open" ? "Live" : connection === "polling" ? "Polling" : "Connecting"}
          </span>
        </div>

        <div className="mt-4 flex items-baseline justify-between">
          <span className="text-2xl font-semibold text-foreground">
            {completedCount}
            <span className="text-muted-foreground/70"> / {PIPELINE_STAGES.length}</span>
          </span>
          <span className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground/70">
            stages complete
          </span>
        </div>

        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-secondary">
          <div
            className="h-full rounded-full bg-foreground transition-[width] duration-700 ease-out"
            style={{ width: `${progress * 100}%` }}
          />
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1 text-[11px] text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5" />
            {isLive ? "Elapsed" : "Duration"} {fmtDuration(elapsedMs)}
          </span>
          <span>{run.steps.length} agent steps</span>
          {tokens > 0 && <span>{tokens.toLocaleString("en-US")} tokens</span>}
        </div>
      </div>

      {/* Stage rail */}
      <div className="relative">
        <span
          aria-hidden
          className="absolute bottom-5 left-[21px] top-5 w-px bg-border"
        />
        <div className="space-y-3">
          {PIPELINE_STAGES.map((stage, idx) => {
            const status = statusFor(idx);
            const steps = stepsByStage[stage.name];
            const stageLatency = steps.reduce((a, s) => a + (s.latency_ms ?? 0), 0);
            const stageTokens = steps.reduce(
              (a, s) => a + (s.tokens_in ?? 0) + (s.tokens_out ?? 0),
              0,
            );
            const summary = artifactSummary(stage.artifact_kind, run.artifacts);
            const detailHere =
              selectedStep != null &&
              stageForNode(selectedStep.node, {
                artifact_kind: selectedStep.input?.artifact_kind as string | undefined,
              }) === stage.name
                ? selectedStep
                : null;
            const showActivity = status === "active";
            const activityForStage =
              activity &&
              stageForNode(activity.node, { stage: activity.stage }) === stage.name
                ? activity.message
                : null;

            return (
              <div key={stage.name} className="relative pl-12">
                {/* Rail marker */}
                <span
                  className={cn(
                    "absolute left-0 top-3 z-10 grid h-11 w-11 place-items-center rounded-full border-2 text-sm font-semibold transition-colors",
                    MARKER[status],
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
                    idx + 1
                  )}
                </span>

                <div
                  className={cn(
                    "glass rounded-2xl p-4 transition-opacity sm:p-5",
                    status === "pending" && "opacity-60",
                  )}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={cn(
                        "text-base font-semibold",
                        status === "pending" ? "text-muted-foreground" : "text-foreground",
                      )}
                    >
                      {stage.label}
                    </span>
                    <span
                      className={cn(
                        "rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.1em]",
                        PILL[status],
                      )}
                    >
                      {STATUS_LABEL[status]}
                    </span>
                  </div>
                  <p className="mt-0.5 text-[12px] leading-relaxed text-muted-foreground">
                    {stage.description}
                  </p>

                  {(steps.length > 0 || summary) && (
                    <p className="mt-1.5 flex flex-wrap items-center gap-x-3 text-[10px] text-muted-foreground/70">
                      {summary && (
                        <span className="font-medium text-muted-foreground">{summary}</span>
                      )}
                      {steps.length > 0 && (
                        <span>
                          {steps.length} step{steps.length === 1 ? "" : "s"}
                        </span>
                      )}
                      {stageLatency > 0 && <span>{(stageLatency / 1000).toFixed(1)}s</span>}
                      {stageTokens > 0 && (
                        <span>{stageTokens.toLocaleString("en-US")} tok</span>
                      )}
                    </p>
                  )}

                  {/* Live activity line */}
                  {showActivity && (
                    <div className="mt-3 flex items-center gap-2 text-[12px] text-foreground">
                      <span className="pulse-active h-2 w-2 shrink-0 rounded-full bg-foreground" />
                      <span className="italic">
                        {activityForStage ?? "Agent is working…"}
                      </span>
                    </div>
                  )}

                  {/* Step chips */}
                  {steps.length > 0 && (
                    <div className="mt-4 flex flex-wrap items-start gap-y-4">
                      {steps.map((step, i) => {
                        const prevDone =
                          i > 0 && steps[i - 1].latency_ms != null && !steps[i - 1].error;
                        return (
                          <Fragment key={stepKey(step)}>
                            {i > 0 && (
                              <span
                                aria-hidden
                                className={cn(
                                  "mt-[15px] h-0.5 w-4 shrink-0 rounded-full sm:w-6",
                                  prevDone ? "bg-foreground/40" : "bg-border",
                                )}
                              />
                            )}
                            <StepChip
                              step={step}
                              index={i + 1}
                              selected={selectedKey === stepKey(step)}
                              onSelect={() =>
                                setSelectedKey((cur) =>
                                  cur === stepKey(step) ? null : stepKey(step),
                                )
                              }
                            />
                          </Fragment>
                        );
                      })}
                    </div>
                  )}

                  {/* Selected step detail */}
                  {detailHere && <StepDetail step={detailHere} />}

                  {/* Human gate renders inline at the paused stage */}
                  {status === "awaiting" && gate && <div className="mt-4">{gate}</div>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function StepChip({
  step,
  index,
  selected,
  onSelect,
}: {
  step: AgentStepView;
  index: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const failed = !!step.error;
  const done = step.latency_ms != null && !failed;
  const score =
    typeof step.output?.score === "number" ? (step.output.score as number) : null;

  const circle = failed
    ? "border-destructive bg-destructive/10 text-destructive"
    : done
      ? "border-foreground bg-foreground text-background"
      : "border-foreground/50 bg-secondary text-foreground";

  const label = step.node.replace(/^review_/, "").replace(/_/g, " ");

  return (
    <button
      onClick={onSelect}
      title={step.node}
      className="flex w-[76px] flex-col items-center gap-1.5 outline-none"
    >
      <span
        className={cn(
          "relative grid h-8 w-8 place-items-center rounded-full border text-xs font-semibold transition-shadow",
          circle,
          selected && "ring-2 ring-ring ring-offset-2 ring-offset-background",
        )}
      >
        {failed ? (
          <AlertTriangle className="h-3.5 w-3.5" />
        ) : done ? (
          <Check className="h-3.5 w-3.5" strokeWidth={2.5} />
        ) : (
          <RotateCw className="h-3.5 w-3.5 animate-spin" />
        )}
        {score != null && (
          <span
            className={cn(
              "absolute -right-1.5 -top-1.5 grid h-4 min-w-4 place-items-center rounded-full border border-background px-0.5 text-[8px] font-bold leading-none",
              score >= 80
                ? "bg-foreground text-background"
                : "bg-amber-500 text-white",
            )}
            title={`Score ${score}/100`}
          >
            {score}
          </span>
        )}
      </span>
      <span
        className={cn(
          "line-clamp-2 text-center text-[9px] font-medium leading-tight",
          selected ? "text-foreground" : "text-muted-foreground",
        )}
      >
        <span className="text-muted-foreground/60">{index}.</span> {label}
      </span>
    </button>
  );
}

function StepDetail({ step }: { step: AgentStepView }) {
  return (
    <div className="mt-4 space-y-3 rounded-xl border border-border/60 bg-secondary/50 p-3.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-semibold text-foreground">
            {step.node}
          </span>
          {step.agent && (
            <span className="rounded-full border border-border bg-card px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
              {step.agent}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground/70">
          {step.latency_ms != null && <span>{(step.latency_ms / 1000).toFixed(1)}s</span>}
          {(step.tokens_in || step.tokens_out) && (
            <span>
              {step.tokens_in ?? 0} in / {step.tokens_out ?? 0} out
            </span>
          )}
        </div>
      </div>

      {step.error && (
        <div className="rounded-md border-l-2 border-destructive bg-destructive/5 p-2 text-[11px] text-destructive">
          {step.error}
        </div>
      )}

      <div>
        <div className="mb-1 text-[9px] font-semibold uppercase tracking-[0.12em] text-muted-foreground/70">
          Output
        </div>
        <pre className="max-h-56 overflow-auto rounded-md bg-secondary p-2.5 font-mono text-[10px] leading-relaxed text-foreground">
          {JSON.stringify(step.output, null, 2)}
        </pre>
      </div>
    </div>
  );
}
