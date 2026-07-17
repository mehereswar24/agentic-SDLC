import { useMemo, useState } from "react";
import { diffLines, type Change } from "diff";
import { ChevronDown, FilePlus2, FileMinus2, FileDiff } from "lucide-react";

import { cn } from "@/lib/utils";
import { jsonToText } from "@/lib/artifact-text";
import type { ArtifactView } from "@/lib/types";

function DiffBlock({ changes }: { changes: Change[] }) {
  return (
    <pre className="max-h-[520px] overflow-auto rounded-xl bg-secondary/50 p-3 font-mono text-[11px] leading-relaxed">
      {changes.map((c, i) => {
        if (c.added) {
          return (
            <span
              key={i}
              className="block border-l-2 border-foreground bg-foreground/[0.07] pl-2 text-foreground"
            >
              {c.value.replace(/\n$/, "").split("\n").map((l, j) => (
                <span key={j} className="block">+ {l}</span>
              ))}
            </span>
          );
        }
        if (c.removed) {
          return (
            <span
              key={i}
              className="block border-l-2 border-destructive pl-2 text-muted-foreground/70 opacity-70"
            >
              {c.value.replace(/\n$/, "").split("\n").map((l, j) => (
                <span key={j} className="block">- {l}</span>
              ))}
            </span>
          );
        }
        return (
          <span key={i} className="block pl-2 text-muted-foreground">
            {c.value.replace(/\n$/, "").split("\n").map((l, j) => (
              <span key={j} className="block">  {l}</span>
            ))}
          </span>
        );
      })}
    </pre>
  );
}

interface FileEntry {
  path: string;
  content: string;
}

function filesOf(artifact: ArtifactView): FileEntry[] | null {
  const c = artifact.content as any;
  const list = artifact.kind === "code" ? c?.files : c?.test_files;
  if (!Array.isArray(list)) return null;
  return list.map((f: any) => ({ path: String(f.path), content: String(f.content ?? "") }));
}

function BundleDiff({ a, b }: { a: FileEntry[]; b: FileEntry[] }) {
  const [openPath, setOpenPath] = useState<string | null>(null);

  const rows = useMemo(() => {
    const aMap = new Map(a.map((f) => [f.path, f.content]));
    const bMap = new Map(b.map((f) => [f.path, f.content]));
    const paths = [...new Set([...aMap.keys(), ...bMap.keys()])].sort();
    return paths
      .map((path) => {
        const inA = aMap.has(path);
        const inB = bMap.has(path);
        const status = !inA ? "added" : !inB ? "removed" : aMap.get(path) === bMap.get(path) ? "same" : "modified";
        return { path, status, a: aMap.get(path) ?? "", b: bMap.get(path) ?? "" };
      })
      .filter((r) => r.status !== "same");
  }, [a, b]);

  if (rows.length === 0) {
    return (
      <p className="rounded-xl border border-border/60 bg-secondary/40 p-4 text-center text-xs text-muted-foreground">
        No file changes between these versions.
      </p>
    );
  }

  return (
    <div className="space-y-1.5">
      {rows.map((r) => (
        <div key={r.path} className="rounded-xl border border-border/60">
          <button
            onClick={() => setOpenPath((p) => (p === r.path ? null : r.path))}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition-colors hover:bg-accent"
          >
            {r.status === "added" ? (
              <FilePlus2 className="h-3.5 w-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
            ) : r.status === "removed" ? (
              <FileMinus2 className="h-3.5 w-3.5 shrink-0 text-destructive" />
            ) : (
              <FileDiff className="h-3.5 w-3.5 shrink-0 text-amber-600 dark:text-amber-400" />
            )}
            <span className="flex-1 truncate font-mono text-foreground">{r.path}</span>
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground/70">
              {r.status}
            </span>
            <ChevronDown
              className={cn(
                "h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform",
                openPath === r.path && "rotate-180",
              )}
            />
          </button>
          {openPath === r.path && (
            <div className="border-t border-border/60 p-2">
              <DiffBlock changes={diffLines(r.a, r.b)} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/**
 * Git-style diff between two versions of one artifact. Structured artifacts
 * diff as jsonToText documents; code/test bundles diff per file.
 */
export function ArtifactDiff({ a, b }: { a: ArtifactView; b: ArtifactView }) {
  const aFiles = filesOf(a);
  const bFiles = filesOf(b);

  if (aFiles && bFiles) {
    return <BundleDiff a={aFiles} b={bFiles} />;
  }

  const changes = diffLines(jsonToText(a.content), jsonToText(b.content));
  const changed = changes.some((c) => c.added || c.removed);
  if (!changed) {
    return (
      <p className="rounded-xl border border-border/60 bg-secondary/40 p-4 text-center text-xs text-muted-foreground">
        These versions are identical.
      </p>
    );
  }
  return <DiffBlock changes={changes} />;
}
