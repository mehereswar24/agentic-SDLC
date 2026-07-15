import type { RunStatus } from "./types";

export const STATUS_META: Record<
  RunStatus,
  { label: string; dot: string; className: string }
> = {
  pending: {
    label: "Pending",
    dot: "bg-muted-foreground",
    className: "bg-muted text-muted-foreground",
  },
  running: {
    label: "Running",
    dot: "bg-foreground animate-pulse",
    className: "bg-foreground/10 text-foreground",
  },
  awaiting_human: {
    label: "Awaiting review",
    dot: "bg-foreground",
    className: "bg-foreground text-background",
  },
  completed: {
    label: "Completed",
    dot: "bg-foreground",
    className: "bg-foreground/90 text-background",
  },
  failed: {
    label: "Failed",
    dot: "bg-destructive",
    className: "bg-destructive/10 text-destructive",
  },
  cancelled: {
    label: "Cancelled",
    dot: "bg-muted-foreground",
    className: "bg-muted text-muted-foreground",
  },
};
