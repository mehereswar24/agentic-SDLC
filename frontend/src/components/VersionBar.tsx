import { GitCompareArrows } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ArtifactView } from "@/lib/types";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export interface CompareSelection {
  a: number;
  b: number;
}

function versionLabel(a: ArtifactView): string {
  const t = new Date(a.created_at);
  return `v${a.version} · ${t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

/** Version picker + compare toggle for one artifact kind. Hidden when there's only one version. */
export function VersionBar({
  versions,
  selected,
  onSelect,
  compare,
  onCompare,
}: {
  versions: ArtifactView[]; // ascending by version
  selected: number;
  onSelect: (v: number) => void;
  compare: CompareSelection | null;
  onCompare: (c: CompareSelection | null) => void;
}) {
  if (versions.length <= 1) return null;
  const latest = versions[versions.length - 1].version;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {!compare ? (
        <>
          <Select
            value={String(selected)}
            onValueChange={(v) => onSelect(Number(v))}
          >
            <SelectTrigger className="h-8 w-[130px] text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {versions.map((a) => (
                <SelectItem key={a.version} value={String(a.version)}>
                  {versionLabel(a)}
                  {a.version === latest ? " · latest" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <button
            onClick={() =>
              onCompare({ a: Math.max(1, selected - 1), b: selected })
            }
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <GitCompareArrows className="h-3.5 w-3.5" />
            Compare
          </button>
        </>
      ) : (
        <>
          {(["a", "b"] as const).map((side) => (
            <Select
              key={side}
              value={String(compare[side])}
              onValueChange={(v) =>
                onCompare({ ...compare, [side]: Number(v) })
              }
            >
              <SelectTrigger className="h-8 w-[120px] text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {versions.map((a) => (
                  <SelectItem key={a.version} value={String(a.version)}>
                    {versionLabel(a)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ))}
          <span className={cn("text-[11px] text-muted-foreground/70")}>
            v{compare.a} ↔ v{compare.b}
          </span>
          <button
            onClick={() => onCompare(null)}
            className="rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            Done
          </button>
        </>
      )}
    </div>
  );
}
