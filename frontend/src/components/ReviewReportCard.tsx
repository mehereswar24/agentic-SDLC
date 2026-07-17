import { useState } from "react";
import { ChevronDown, ShieldCheck, ShieldAlert } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ReviewReport } from "@/lib/types";

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"] as const;

const SEVERITY_DOT: Record<string, string> = {
  critical: "bg-red-600",
  high: "bg-red-400",
  medium: "bg-amber-500",
  low: "bg-muted-foreground",
  info: "bg-muted-foreground/50",
};

const REVIEWER_LABEL: Record<string, string> = {
  planner_reviewer: "PRD review",
  architecture_reviewer: "Architecture review",
  security_reviewer: "Security review",
};

export function ReviewReportCard({ report }: { report: ReviewReport }) {
  const [open, setOpen] = useState(false);
  const findings = [...(report.findings ?? [])].sort(
    (a, b) =>
      SEVERITY_ORDER.indexOf((a.severity as any) ?? "info") -
      SEVERITY_ORDER.indexOf((b.severity as any) ?? "info"),
  );
  const label = REVIEWER_LABEL[report.reviewer] ?? report.reviewer;

  return (
    <div className="rounded-xl border border-border/60 bg-secondary/40 p-3.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {report.passed ? (
            <ShieldCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
          ) : (
            <ShieldAlert className="h-4 w-4 text-amber-600 dark:text-amber-400" />
          )}
          <span className="text-xs font-semibold text-foreground">{label}</span>
          <span
            className={cn(
              "rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.1em]",
              report.passed
                ? "border-border bg-secondary text-muted-foreground"
                : "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
            )}
          >
            {report.passed ? "Passed" : "Needs attention"}
          </span>
        </div>
        <span className="text-sm font-semibold tabular-nums text-foreground">
          {report.score}
          <span className="text-[10px] font-normal text-muted-foreground/70">/100</span>
        </span>
      </div>

      {report.summary && (
        <p className="mt-2 text-[12px] leading-relaxed text-muted-foreground">
          {report.summary}
        </p>
      )}

      {findings.length > 0 && (
        <div className="mt-2">
          <button
            onClick={() => setOpen((o) => !o)}
            className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <ChevronDown
              className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")}
            />
            {findings.length} finding{findings.length === 1 ? "" : "s"}
          </button>

          {open && (
            <ul className="mt-2 space-y-2">
              {findings.map((f, i) => (
                <li key={i} className="flex items-start gap-2 text-[12px]">
                  <span
                    className={cn(
                      "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                      SEVERITY_DOT[(f.severity as string) ?? "info"] ??
                        SEVERITY_DOT.info,
                    )}
                    title={String(f.severity ?? "info")}
                  />
                  <span className="text-muted-foreground">
                    <span className="font-medium text-foreground">
                      {f.category ? `${f.category}: ` : ""}
                    </span>
                    {f.description}
                    {f.suggestion && (
                      <span className="block text-[11px] text-muted-foreground/70">
                        ↳ {f.suggestion}
                      </span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
