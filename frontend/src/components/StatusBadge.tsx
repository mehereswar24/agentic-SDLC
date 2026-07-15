import type { RunStatus } from "@/lib/types";

const PILL: Record<RunStatus, string> = {
  pending: "border-line bg-surface-2 text-muted",
  running: "border-accent/40 bg-accent-soft text-accent-ink",
  awaiting_human:
    "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  completed:
    "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  failed: "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300",
  cancelled: "border-line bg-surface-2 text-faint",
};

const DOT: Record<RunStatus, string> = {
  pending: "bg-faint",
  running: "animate-pulse bg-accent",
  awaiting_human: "bg-amber-500",
  completed: "bg-emerald-500",
  failed: "bg-red-500",
  cancelled: "bg-faint",
};

export function StatusBadge({ status }: { status: RunStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.14em] ${PILL[status]}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${DOT[status]}`} />
      {status.replace("_", " ")}
    </span>
  );
}
