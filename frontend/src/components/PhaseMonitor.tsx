import { Fragment, useEffect, useState } from "react";
import { AlertTriangle, Check, Clock, Hourglass, RotateCw } from "lucide-react";

import { cn } from "@/lib/cn";
import type { AgentStepView, Critique, RunDetail } from "@/lib/types";

type PhaseKey = "plan" | "design" | "build";
type PhaseStatus = "pending" | "active" | "awaiting" | "completed" | "failed";

const ORDER: PhaseKey[] = ["plan", "design", "build"];

const PHASE_META: Record<PhaseKey, { title: string; subtitle: string; numeral: string }> = {
  plan: { title: "Plan", subtitle: "Draft, critique & revise the PRD", numeral: "1" },
  design: {
    title: "Design",
    subtitle: "Architecture, data models & integrations",
    numeral: "2",
  },
  build: { title: "Build", subtitle: "Generate the runnable codebase", numeral: "3" },
};

const STATUS_LABEL: Record<PhaseStatus, string> = {
  pending: "Pending",
  active: "In progress",
  awaiting: "Awaiting approval",
  completed: "Completed",
  failed: "Failed",
};

const STATUS_PILL: Record<PhaseStatus, string> = {
  pending: "border-line bg-surface-2 text-faint",
  active: "border-accent/40 bg-accent-soft text-accent-ink",
  awaiting: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  completed:
    "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  failed: "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300",
};

const MARKER: Record<PhaseStatus, string> = {
  pending: "border-line bg-surface text-faint",
  active: "border-accent bg-accent-soft text-accent",
  awaiting: "border-amber-500 bg-amber-500/15 text-amber-600 dark:text-amber-400",
  completed: "border-accent bg-accent text-white",
  failed: "border-red-500 bg-red-500/15 text-red-500",
};

function phaseOf(node: string): PhaseKey {
  const n = node.toLowerCase();
  if (n.includes("design")) return "design";
  if (n.includes("cod") || n.includes("build") || n.includes("implement")) return "build";
  return "plan";
}

function fmtDuration(ms: number): string {
  const total = Math.floor(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function stepKey(s: AgentStepView): string {
  return `${s.id}-${s.created_at}`;
}

export function PhaseMonitor({
  run,
  connection,
}: {
  run: RunDetail;
  connection: "connecting" | "open" | "closed";
}) {
  const completed: Record<PhaseKey, boolean> = {
    plan: run.artifacts.some((a) => a.kind === "prd"),
    design: run.artifacts.some((a) => a.kind === "system_design"),
    build: run.artifacts.some((a) => a.kind === "code"),
  };
  const frontierIdx = ORDER.findIndex((k) => !completed[k]); // -1 when all done

  const statusFor = (idx: number): PhaseStatus => {
    const key = ORDER[idx];
    if (completed[key]) return "completed";
    if (idx !== frontierIdx) return "pending";
    switch (run.status) {
      case "failed":
        return "failed";
      case "awaiting_human":
        return "awaiting";
      case "running":
        return "active";
      default:
        return "pending";
    }
  };

  const stepsByPhase: Record<PhaseKey, AgentStepView[]> = {
    plan: [],
    design: [],
    build: [],
  };
  for (const s of run.steps) stepsByPhase[phaseOf(s.node)].push(s);

  const isLive = run.status === "running" || run.status === "awaiting_human";

  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  // Live elapsed clock.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!isLive) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [isLive]);

  const startMs = new Date(run.created_at).getTime();
  const endMs = isLive ? now : new Date(run.updated_at).getTime();
  const elapsedMs = Math.max(0, endMs - startMs);

  const completedCount = ORDER.filter((k) => completed[k]).length;
  const activeFraction = run.status === "running" && frontierIdx >= 0 ? 0.5 : 0;
  const progress = Math.min(1, (completedCount + activeFraction) / ORDER.length);

  const tokensIn = run.steps.reduce((s, x) => s + (x.tokens_in ?? 0), 0);
  const tokensOut = run.steps.reduce((s, x) => s + (x.tokens_out ?? 0), 0);

  const selectedStep =
    selectedKey != null
      ? run.steps.find((s) => stepKey(s) === selectedKey) ?? null
      : null;

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="card p-5">
        <div className="flex items-center justify-between gap-3">
          <h3 className="eyebrow">Phase monitor</h3>
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
            {completedCount}
            <span className="text-faint"> / {ORDER.length}</span>
          </span>
          <span className="text-[11px] uppercase tracking-[0.12em] text-faint">
            phases complete
          </span>
        </div>

        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-700 ease-out"
            style={{ width: `${progress * 100}%` }}
          />
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1 text-[11px] text-muted">
          <span className="inline-flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5 text-accent" />
            {isLive ? "Elapsed" : "Duration"} {fmtDuration(elapsedMs)}
          </span>
          <span>{run.steps.length} agent steps</span>
          {(tokensIn > 0 || tokensOut > 0) && (
            <span>
              {tokensIn.toLocaleString("en-US")} in / {tokensOut.toLocaleString("en-US")}{" "}
              out tokens
            </span>
          )}
        </div>
      </div>

      {/* Phase pipelines */}
      {ORDER.map((key, idx) => {
        const status = statusFor(idx);
        const meta = PHASE_META[key];
        const steps = stepsByPhase[key];
        const phaseLatency = steps.reduce((s, x) => s + (x.latency_ms ?? 0), 0);
        const phaseTokens = steps.reduce(
          (s, x) => s + (x.tokens_in ?? 0) + (x.tokens_out ?? 0),
          0,
        );
        const detailHere =
          selectedStep != null && phaseOf(selectedStep.node) === key
            ? selectedStep
            : null;

        return (
          <div key={key} className="card p-4 sm:p-5">
            {/* Phase header */}
            <div className="flex items-start gap-3">
              <span
                className={cn(
                  "grid h-9 w-9 shrink-0 place-items-center rounded-full border text-sm font-semibold",
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
                  meta.numeral
                )}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={cn(
                      "font-display text-base font-semibold",
                      status === "pending" ? "text-muted" : "text-ink",
                    )}
                  >
                    {meta.title}
                  </span>
                  <span
                    className={cn(
                      "rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.1em]",
                      STATUS_PILL[status],
                    )}
                  >
                    {STATUS_LABEL[status]}
                  </span>
                </div>
                <p className="mt-0.5 text-[12px] leading-relaxed text-muted">
                  {meta.subtitle}
                </p>
                {steps.length > 0 && (
                  <p className="mt-1 flex flex-wrap items-center gap-x-3 text-[10px] text-faint">
                    <span>
                      {steps.length} step{steps.length === 1 ? "" : "s"}
                    </span>
                    {phaseLatency > 0 && <span>{(phaseLatency / 1000).toFixed(1)}s</span>}
                    {phaseTokens > 0 && (
                      <span>{phaseTokens.toLocaleString("en-US")} tok</span>
                    )}
                  </p>
                )}
              </div>
            </div>

            {/* Step pipeline */}
            <div className="mt-4 pl-1">
              {steps.length === 0 ? (
                <p className="text-[11px] text-faint">
                  {status === "active"
                    ? "Agent is starting…"
                    : status === "pending"
                      ? "Waiting for earlier phases to finish."
                      : "No steps recorded."}
                </p>
              ) : (
                <div className="flex flex-wrap items-start gap-y-4">
                  {steps.map((step, i) => {
                    const prevDone =
                      i > 0 && steps[i - 1].latency_ms != null && !steps[i - 1].error;
                    return (
                      <Fragment key={stepKey(step)}>
                        {i > 0 && (
                          <span
                            aria-hidden
                            className={cn(
                              "mt-[17px] h-0.5 w-5 shrink-0 rounded-full sm:w-7",
                              prevDone ? "bg-accent/50" : "bg-line",
                            )}
                          />
                        )}
                        <StepCircle
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
                  {status === "active" && (
                    <>
                      <span
                        aria-hidden
                        className="mt-[17px] h-0.5 w-5 shrink-0 rounded-full bg-line sm:w-7"
                      />
                      <div className="flex w-[72px] flex-col items-center gap-1.5">
                        <span className="grid h-9 w-9 place-items-center rounded-full border border-dashed border-accent/60 text-accent">
                          <RotateCw className="h-4 w-4 animate-spin" />
                        </span>
                        <span className="text-center text-[9px] leading-tight text-accent-ink">
                          working…
                        </span>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Selected step detail */}
            {detailHere && <StepDetail step={detailHere} />}
          </div>
        );
      })}
    </div>
  );
}

function StepCircle({
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
  const critique =
    step.node === "planner_critique"
      ? (step.output.critique as Critique | undefined)
      : undefined;

  const circle = failed
    ? "border-red-500 bg-red-500/15 text-red-500"
    : done
      ? "border-accent bg-accent text-white"
      : "border-accent/60 bg-accent-soft text-accent";

  // Strip a leading agent prefix so labels read cleanly (planner_critique → critique).
  const label = step.node.replace(/^(planner|designer|coder)_?/, "") || step.node;

  return (
    <button
      onClick={onSelect}
      title={step.node}
      className="flex w-[72px] flex-col items-center gap-1.5 outline-none"
    >
      <span
        className={cn(
          "relative grid h-9 w-9 place-items-center rounded-full border text-xs font-semibold transition-shadow",
          circle,
          selected && "ring-2 ring-accent ring-offset-2 ring-offset-surface",
        )}
      >
        {failed ? (
          <AlertTriangle className="h-4 w-4" />
        ) : done ? (
          <Check className="h-4 w-4" strokeWidth={2.5} />
        ) : (
          <RotateCw className="h-4 w-4 animate-spin" />
        )}
        {critique && (
          <span
            className={cn(
              "absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full border px-0.5 text-[8px] font-bold leading-none",
              critique.score >= 80
                ? "border-emerald-500/40 bg-emerald-500 text-white"
                : "border-amber-500/40 bg-amber-500 text-white",
            )}
            title={`Critique score ${critique.score}/100`}
          >
            {critique.score}
          </span>
        )}
      </span>
      <span
        className={cn(
          "line-clamp-2 text-center text-[9px] font-medium leading-tight",
          selected ? "text-ink" : "text-muted",
        )}
      >
        <span className="text-faint">{index}.</span> {label}
      </span>
    </button>
  );
}

function StepDetail({ step }: { step: AgentStepView }) {
  const critique =
    step.node === "planner_critique"
      ? (step.output.critique as Critique | undefined)
      : undefined;

  return (
    <div className="mt-4 space-y-3 rounded-lg border border-line-soft bg-surface-2 p-3.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-semibold text-ink">{step.node}</span>
          {step.agent && (
            <span className="rounded-full border border-accent/30 bg-accent-soft px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-[0.1em] text-accent-ink">
              {step.agent}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-[10px] text-faint">
          {step.latency_ms != null && <span>{(step.latency_ms / 1000).toFixed(1)}s</span>}
          {(step.tokens_in || step.tokens_out) && (
            <span>
              {step.tokens_in ?? 0} in / {step.tokens_out ?? 0} out
            </span>
          )}
        </div>
      </div>

      {step.error && (
        <div className="rounded-md border-l-2 border-red-500 bg-red-500/5 p-2 text-[11px] text-red-600 dark:text-red-300">
          {step.error}
        </div>
      )}

      {critique && (
        <div className="space-y-1.5 text-[12px] text-muted">
          <p className="font-display italic text-body">"{critique.summary}"</p>
          {critique.issues?.length > 0 && (
            <ul className="list-disc space-y-0.5 pl-4 marker:text-accent">
              {critique.issues.map((issue, idx) => (
                <li key={idx}>{issue}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div>
        <div className="mb-1 text-[9px] font-bold uppercase tracking-[0.12em] text-faint">
          Raw output
        </div>
        <pre className="max-h-56 overflow-auto rounded-md p-2.5 font-mono text-[10px] leading-relaxed [background:var(--code-bg)] [color:var(--code-fg)]">
          {JSON.stringify(step.output, null, 2)}
        </pre>
      </div>
    </div>
  );
}
