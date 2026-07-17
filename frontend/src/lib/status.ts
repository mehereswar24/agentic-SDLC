import type { RunStatus } from "./types";

// Single source of truth for run-status styling. Pills stay monochrome
// (loaded liquid-glass tokens); only the dot carries a small amount of hue.
export const STATUS_META: Record<
  RunStatus,
  { label: string; dot: string; pill: string }
> = {
  pending: {
    label: "Pending",
    dot: "bg-muted-foreground/60",
    pill: "border-border bg-secondary text-muted-foreground",
  },
  running: {
    label: "Running",
    dot: "animate-pulse bg-foreground",
    pill: "border-foreground/20 bg-foreground/10 text-foreground",
  },
  awaiting_human: {
    label: "Awaiting review",
    dot: "bg-amber-500",
    pill: "border-border bg-secondary text-foreground",
  },
  completed: {
    label: "Completed",
    dot: "bg-emerald-500",
    pill: "border-border bg-secondary text-muted-foreground",
  },
  failed: {
    label: "Failed",
    dot: "bg-red-500",
    pill: "border-destructive/30 bg-destructive/10 text-destructive",
  },
  cancelled: {
    label: "Cancelled",
    dot: "bg-muted-foreground/60",
    pill: "border-border bg-secondary text-muted-foreground/70",
  },
};
