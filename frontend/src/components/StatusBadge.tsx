import type { RunStatus } from "@/lib/types";
import { STATUS_META } from "@/lib/status";
import { cn } from "@/lib/utils";

export function StatusBadge({
  status,
  size = "md",
}: {
  status: RunStatus;
  size?: "sm" | "md";
}) {
  const meta = STATUS_META[status];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border font-semibold uppercase tracking-[0.14em]",
        size === "sm"
          ? "gap-1 px-2 py-px text-[8px]"
          : "gap-1.5 px-2.5 py-0.5 text-[9px]",
        meta.pill,
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", meta.dot)} />
      {meta.label}
    </span>
  );
}
