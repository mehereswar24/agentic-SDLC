import { useState } from "react";
import { Activity, ArrowDownToLine, ArrowUpFromLine, Timer } from "lucide-react";

import { api } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import type { Stats } from "@/lib/types";

function formatThousands(n: number): string {
  return n.toLocaleString("en-US");
}

export function StatsWidget() {
  const [stats, setStats] = useState<Stats | null>(null);

  usePolling(async () => {
    try {
      setStats(await api.stats());
    } catch {
      /* ignore — widget is best-effort */
    }
  }, 10_000);

  if (!stats || stats.total_runs === 0) return null;

  return (
    <div className="space-y-3">
      <h3 className="eyebrow">Pipeline analytics</h3>
      <dl className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
        <Cell
          icon={<Activity className="h-3.5 w-3.5" />}
          label="Runs"
          value={formatThousands(stats.total_runs)}
          sublabel={`${stats.by_status.completed} completed`}
        />
        <Cell
          icon={<ArrowDownToLine className="h-3.5 w-3.5" />}
          label="Tokens in"
          value={formatThousands(stats.tokens_in_total)}
        />
        <Cell
          icon={<ArrowUpFromLine className="h-3.5 w-3.5" />}
          label="Tokens out"
          value={formatThousands(stats.tokens_out_total)}
        />
        <Cell
          icon={<Timer className="h-3.5 w-3.5" />}
          label="Avg step"
          value={`${(stats.avg_step_latency_ms / 1000).toFixed(1)}s`}
        />
      </dl>
    </div>
  );
}

function Cell({
  icon,
  label,
  value,
  sublabel,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sublabel?: string;
}) {
  return (
    <div className="panel p-4">
      <dt className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-faint">
        <span className="text-accent">{icon}</span>
        {label}
      </dt>
      <dd className="mt-1.5 font-display text-lg font-semibold text-ink">{value}</dd>
      {sublabel ? (
        <dd className="mt-0.5 text-[10px] text-faint">{sublabel}</dd>
      ) : null}
    </div>
  );
}
